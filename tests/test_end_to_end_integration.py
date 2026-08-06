import os
import time
import unittest
import unicodedata
import uuid
from dataclasses import replace
from pathlib import Path

import gspread
from gspread.exceptions import WorksheetNotFound

from app.config import load_config, load_dotenv_file, load_google_credentials
from app.email_client import EmailClient
from app.ia_clients import GeminiIAClient, LocalIAClient, OpenRouterIAClient
from app.main import run
from tests.fixtures.appointment_emails import APPOINTMENT_FIXTURES


@unittest.skipUnless(
    os.getenv("RUN_END_TO_END_INTEGRATION_TESTS") == "1",
    "Set RUN_END_TO_END_INTEGRATION_TESTS=1 to run the real end-to-end test",
)
class EndToEndIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path(".env.test").is_file():
            raise unittest.SkipTest("Create .env.test before running the E2E test")
        load_dotenv_file(".env.test")
        # Keep .env.test authoritative while allowing it to contain only the
        # test-specific values.
        load_dotenv_file(".env")
        cls.config = load_config()
        cls.ia_provider = os.getenv("E2E_IA_PROVIDER", "local").strip().lower()
        if cls.ia_provider not in {"local", "gemini", "openrouter"}:
            raise unittest.SkipTest(
                "E2E_IA_PROVIDER must be one of: local, gemini, openrouter"
            )
        if cls.ia_provider == "gemini" and not cls.config.gemini_ia_api_key:
            raise unittest.SkipTest("GEMINI_IA_API_KEY must be configured")
        if cls.ia_provider == "openrouter" and not (
            cls.config.openrouter_api_key and cls.config.open_router_model
        ):
            raise unittest.SkipTest(
                "OPENROUTER_API_KEY and OPEN_ROUTER_MODEL must be configured"
            )
        test_sheet_id = cls.config.database["sheet_id"]
        if not test_sheet_id:
            raise unittest.SkipTest("SHEET_ID must be configured in .env.test")
        cls.credentials = load_google_credentials(
            cls.config.database["credentials"]
        )
        cls.spreadsheet = gspread.service_account_from_dict(cls.credentials).open_by_key(
            test_sheet_id
        )
        cls.sheet = cls.spreadsheet.worksheet(
            cls.config.database["table_name"]
        )
        try:
            cls.email_sheet = cls.spreadsheet.worksheet(
                cls.config.database["email_table_name"]
            )
        except WorksheetNotFound:
            raise unittest.SkipTest(
                f"The test spreadsheet must contain a {cls.config.database['email_table_name']} worksheet"
            )

    def test_email_to_selected_ia_to_sheets_and_reply(self):
        marker = uuid.uuid4().hex[:12]
        subjects = [
            f"{self._ascii_subject(fixture.email.subject)} [E2E-{marker}-{index}]"
            for index, fixture in enumerate(APPOINTMENT_FIXTURES[2:])
        ]
        reply_subjects = [f"Re: {subject}" for subject in subjects]

        self.addCleanup(
            self._cleanup_test_data,
            *[value for pair in zip(subjects, reply_subjects) for value in pair],
            marker,
        )

        # Process each real-world-shaped example separately so the E2E run
        # exercises subject-based patient names and multi-study messages.
        for fixture, subject, reply_subject in zip(
            APPOINTMENT_FIXTURES[2:], subjects, reply_subjects
        ):
            mail = fixture.email
            expected_count = len(fixture.extracted)
            self._send_email(subject, mail.body)
            received = self._wait_for_email(subject, self.config.imap["folder"])
            self.assertIsNotNone(received, f"The E2E email was not received: {subject}")

            test_config = replace(
                self.config,
                local_ia_enabled=self.ia_provider == "local",
                imap={
                    **self.config.imap,
                    "search": f'HEADER Subject "{subject}"',
                },
                allowed_senders=self.config.allowed_senders
                | {self.config.smtp["username"].lower()},
            )
            run(
                config=test_config,
                max_cycles=1,
                sleep=lambda _: None,
                **{
                    f"{self.ia_provider}_ia_client_factory": self._printing_ia_client_factory()
                },
                ia_provider=self.ia_provider,
            )

            processed = self._wait_for_email(subject, self.config.processed_folder)
            self.assertIsNotNone(processed, f"The E2E email was not processed: {subject}")
            reply = self._wait_for_email(reply_subject, self.config.imap["folder"])
            self.assertIsNotNone(reply, f"The success reply was not received: {subject}")
            self.assertIn("agregado correctamente", reply.body)

            appointment_rows = self._wait_for_rows(
                self.sheet,
                lambda row: self._row_contains(row, marker, subject),
            )
            self.assertEqual(len(appointment_rows), expected_count)
            self.assertTrue(
                all(row[13] for row in appointment_rows),
                "An appointment URL was not populated",
            )

            email_rows = self._wait_for_rows(
                self.email_sheet,
                lambda row: self._row_contains(row, marker, subject),
            )
            self.assertEqual(len(email_rows), 1)
            self.assertTrue(email_rows[0][5], "The email URL was not populated")
            stored_body = email_rows[0][-1].replace("\r\n", "\n")
            self.assertIn(mail.body, stored_body)

    def _cleanup_test_data(self, *values):
        marker = values[-1]
        subject_pairs = zip(values[:-1:2], values[1:-1:2])
        if os.getenv("KEEP_END_TO_END_DATA") != "1":
            self._clean_emails(
                *(subject for pair in subject_pairs for subject in pair)
            )
            self._clean_sheet_rows(marker)

    @staticmethod
    def _ascii_subject(subject):
        normalized = unicodedata.normalize("NFKD", subject)
        return normalized.encode("ascii", "ignore").decode("ascii").replace("–", "-")

    def _printing_ia_client_factory(self):
        client_factories = {
            "local": LocalIAClient,
            "gemini": GeminiIAClient,
            "openrouter": OpenRouterIAClient,
        }
        client_factory = client_factories[self.ia_provider]
        provider = self.ia_provider.upper()

        def factory(*args, **kwargs):
            client = client_factory(*args, **kwargs)
            generate_structured_output = client.generate_structured_output

            def generate(prompt, response_schema):
                response = generate_structured_output(prompt, response_schema)
                print(f"[{provider} IA RESPONSE]")
                print(response.model_dump_json(indent=2))
                print(f"[/{provider} IA RESPONSE]", flush=True)
                return response

            client.generate_structured_output = generate
            return client

        return factory

    def _wait_for_rows(self, worksheet, predicate):
        deadline = time.monotonic() + int(
            os.getenv("SHEETS_INTEGRATION_TIMEOUT_SECONDS", "30")
        )
        while time.monotonic() < deadline:
            matching_rows = [
                row for row in worksheet.get_all_values() if predicate(row)
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

    def _client(self, folder=None, search=None):
        imap = dict(self.config.imap)
        if folder is not None:
            imap["folder"] = folder
        if search is not None:
            imap["search"] = search
        return EmailClient(
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

    def _clean_emails(self, *subjects):
        for folder in {
            self.config.imap["folder"],
            self.config.processed_folder,
            self.config.failed_folder,
        }:
            for subject in subjects:
                try:
                    with self._client(
                        folder=folder,
                        search="ALL",
                    ) as client:
                        for email in client.fetch(100):
                            if email.subject == subject:
                                client.delete(email)
                except Exception:
                    pass

    def _clean_sheet_rows(self, marker):
        for worksheet in (self.sheet, self.email_sheet):
            rows = worksheet.get_all_values()
            row_numbers = [
                index
                for index, row in enumerate(rows, start=1)
                if self._row_contains(row, marker)
            ]
            for row_number in reversed(row_numbers):
                worksheet.delete_rows(row_number)


if __name__ == "__main__":
    unittest.main()
