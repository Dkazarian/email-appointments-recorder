import os
import time
import unittest
import unicodedata
import uuid
from dataclasses import replace
from pathlib import Path

from app.appointments_sheet import AppointmentsSheet
from app.config import load_config, load_dotenv_file, load_google_credentials
from app.email_client import AppointmentsEmailClient
from app.ai_clients import GoogleAIStudioClient, LocalAIClient, OpenRouterAIClient
from app.main import run
from tests.fixtures.appointment_emails import APPOINTMENT_FIXTURES


@unittest.skipUnless(
    os.getenv("RUN_END_TO_END_INTEGRATION_TESTS") == "1",
    "Set RUN_END_TO_END_INTEGRATION_TESTS=1 to run the real end-to-end test",
)
class EndToEndIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._load_config()
        cls._load_ai_provider()
        cls._load_sheets()


    def test_email_to_selected_ai_to_sheets_and_reply(self):
        run_marker = uuid.uuid4().hex[:12]
        subjects = [
            f"{self._ascii_subject(fixture.email.subject)} [E2E-{run_marker}-{index}]"
            for index, fixture in enumerate(APPOINTMENT_FIXTURES)
        ]
        reply_subjects = [f"Re: {subject}" for subject in subjects]
        self.addCleanup(self._cleanup_test_data, subjects + reply_subjects)

        for fixture, subject, reply_subject in zip(
            APPOINTMENT_FIXTURES, subjects, reply_subjects
        ):
            mail = fixture.email
            expected_count = len(fixture.extracted)
            self._send_email(subject, mail.body)

            self._run_app(subject)

            self._assert_email_processed_and_replied(subject, reply_subject)

            self._assert_appointments_in_sheet(
                mail, subject, fixture.extracted, expected_count
            )

    def _assert_email_processed_and_replied(self, subject, reply_subject):
        processed = self._wait_for_email(subject, self.config.processed_folder)
        self.assertIsNotNone(processed, f"The E2E email was not processed: {subject}")
        reply = self._wait_for_email(reply_subject, self.config.imap["folder"])
        self.assertIsNotNone(reply, f"The success reply was not received: {subject}")
        self.assertIn("agregados correctamente", reply.body)

    def _assert_appointments_in_sheet(
        self, mail, subject, expected_appointments, expected_count
    ):
        appointment_rows = self._wait_for_rows(
            self.sheets.get_rows,
            lambda row: self._row_contains(row, subject),
        )
        self.assertEqual(len(appointment_rows), expected_count)
        unmatched_rows = list(appointment_rows)
        for expected in expected_appointments:
            match_index = next(
                (
                    index
                    for index, row in enumerate(unmatched_rows)
                    if row[0] == (expected.patient_name or "")
                    and expected.study.casefold() in row[1].casefold()
                    and row[4] == (expected.date or "")
                    and self._normalize_time(row[5])
                    == self._normalize_time(expected.time)
                ),
                None,
            )
            self.assertIsNotNone(
                match_index,
                f"Unexpected appointment row for {expected!r}: {appointment_rows}",
            )
            unmatched_rows.pop(match_index)
        self.assertFalse(unmatched_rows)
        self.assertTrue(
            all(row[13] for row in appointment_rows),
            "An appointment URL was not populated",
        )
        email_rows = self._wait_for_rows(
            lambda: self.sheets.get_rows(self.config.database["email_table_name"]),
            lambda row: self._row_contains(row, subject),
        )
        self.assertEqual(len(email_rows), 1)
        self.assertTrue(email_rows[0][5], "The email URL was not populated")
        stored_body = email_rows[0][-1].replace("\r\n", "\n")
        self.assertIn(mail.body, stored_body)

    @staticmethod
    def _normalize_time(value):
        if not value:
            return ""
        parts = value.split(":")
        if len(parts) == 2:
            parts.append("00")
        return f"{int(parts[0])}:{parts[1]}:{parts[2]}"

    def _run_app(self, subject):
        config = replace(
            self.config,
            imap={**self.config.imap, "search": f'HEADER Subject "{subject}"'},
            allowed_senders=self.config.allowed_senders
            | {self.config.smtp["username"].lower()},
        )

        run(
            config=config,
            max_cycles=1,
            sleep=lambda _: None,
            **{
                {
                    "local": "local_ai_client_factory",
                    "google_ai_studio": "google_ai_studio_client_factory",
                    "openrouter": "openrouter_ai_client_factory",
                }[self.ai_provider]: self._printing_ai_client_factory()
            },
            ai_provider=self.ai_provider,
        )

    @staticmethod
    def _ascii_subject(subject):
        normalized = unicodedata.normalize("NFKD", subject)
        return normalized.encode("ascii", "ignore").decode("ascii").replace("–", "-")

    def _cleanup_test_data(self, subjects):
        if os.getenv("KEEP_END_TO_END_DATA") != "1":
            self._clean_emails(subjects)
            self._clean_sheet_rows(subjects)

    def _clean_emails(self, subjects):
        for folder in {
            self.config.imap["folder"],
            self.config.processed_folder,
            self.config.failed_folder,
        }:
            try:
                with self._client(folder=folder, search="ALL") as client:
                    for email in client.fetch(100):
                        if email.subject in subjects:
                            client.delete(email)
            except Exception:
                # Cleanup must not hide the original test failure.
                pass

    def _clean_sheet_rows(self, subjects):
        for table_name in (
            self.config.database["table_name"],
            self.config.database["email_table_name"],
        ):
            try:
                rows = self.sheets.get_rows(table_name)
                row_numbers = [
                    index
                    for index, row in enumerate(rows, start=1)
                    if any(self._row_contains(row, subject) for subject in subjects)
                ]
                self.sheets.delete_rows(row_numbers, table_name)
            except Exception:
                # Cleanup must not hide the original test failure.
                pass


    def _printing_ai_client_factory(self):
        client_factories = {
            "local": LocalAIClient,
            "google_ai_studio": GoogleAIStudioClient,
            "openrouter": OpenRouterAIClient,
        }
        client_factory = client_factories[self.ai_provider]
        provider = self.ai_provider.upper()

        def factory(*args, **kwargs):
            client = client_factory(*args, **kwargs)
            generate_structured_output = client.generate_structured_output

            def generate_structured_output_and_print(prompt, response_schema):
                response = generate_structured_output(prompt, response_schema)
                print(f"[{provider} AI RESPONSE]")
                print(response.model_dump_json(indent=2))
                print(f"[/{provider} AI RESPONSE]", flush=True)
                return response

            client.generate_structured_output = generate_structured_output_and_print
            return client

        return factory

    def _wait_for_rows(self, rows_factory, predicate):
        deadline = time.monotonic() + int(
            os.getenv("SHEETS_INTEGRATION_TIMEOUT_SECONDS", "30")
        )
        while time.monotonic() < deadline:
            matching_rows = [
                row for row in rows_factory() if predicate(row)
            ]
            if matching_rows:
                return matching_rows
            time.sleep(2)
        return []

    @staticmethod
    def _row_contains(row, *needles):
        return all(any(needle in value for value in row) for needle in needles)

    def _send_email(self, subject: str, body: str) -> None:
        self._client().send(self.config.imap["username"], subject, body)
        received = self._wait_for_email(subject, self.config.imap["folder"])
        self.assertIsNotNone(received, f"The E2E email was not received: {subject}")

    def _client(self, folder=None, search=None):
        imap = dict(self.config.imap)
        if folder is not None:
            imap["folder"] = folder
        if search is not None:
            imap["search"] = search
        return AppointmentsEmailClient(
            imap,
            self.config.smtp,
            self.config.processed_folder,
            self.config.failed_folder,
            self.config.allowed_senders
            | {self.config.smtp["username"].lower()},
        )

    def _wait_for_email(self, subject, folder):
        deadline = time.monotonic() + int(
            os.getenv("EMAIL_INTEGRATION_TIMEOUT_SECONDS", "60")
        )
        while time.monotonic() < deadline:
            with self._client(
                folder=folder,
                search="ALL",
            ) as client:
                email = next(
                    (mail for mail in client.fetch(100) if mail.subject == subject),
                    None,
                )
            if email:
                return email
            time.sleep(2)
        return None


    @classmethod
    def _load_config(cls):
        if not Path(".env.test").is_file():
            raise unittest.SkipTest("Create .env.test before running the E2E test")
        load_dotenv_file(".env.test")
        # Keep .env.test authoritative while allowing it to contain only the
        # test-specific values.
        load_dotenv_file(".env")
        cls.config = load_config()

    @classmethod
    def _load_ai_provider(cls):
        cls.ai_provider = os.getenv("E2E_AI_PROVIDER", "local").strip().lower()
        if cls.ai_provider not in {"local", "google_ai_studio", "openrouter"}:
            raise unittest.SkipTest(
                "E2E_AI_PROVIDER must be one of: local, google_ai_studio, openrouter"
            )
        if cls.ai_provider == "google_ai_studio" and not cls.config.google_ai_studio_api_key:
            raise unittest.SkipTest("GOOGLE_AI_STUDIO_API_KEY must be configured")
        if cls.ai_provider == "openrouter" and not (
            cls.config.openrouter_api_key and cls.config.open_router_model
        ):
            raise unittest.SkipTest(
                "OPENROUTER_API_KEY and OPEN_ROUTER_MODEL must be configured"
            )

    @classmethod
    def _load_sheets(cls):
        test_sheet_id = cls.config.database["sheet_id"]
        if not test_sheet_id:
            raise unittest.SkipTest("SHEET_ID must be configured in .env.test")
        cls.credentials = load_google_credentials(cls.config.database["credentials"])
        cls.sheets = AppointmentsSheet(
            cls.credentials,
            test_sheet_id,
            cls.config.database["table_name"],
            cls.config.database["email_table_name"],
        )
        try:
            cls.sheets.get_rows(cls.config.database["email_table_name"])
        except Exception as error:
            raise unittest.SkipTest(
                f"The test spreadsheet must contain a {cls.config.database['email_table_name']} worksheet"
            ) from error

if __name__ == "__main__":
    unittest.main()
