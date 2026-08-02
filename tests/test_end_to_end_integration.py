import os
import time
import unittest
import uuid
from dataclasses import replace
from pathlib import Path

import gspread
from gspread.exceptions import WorksheetNotFound

from app.config import load_config, load_dotenv_file, load_google_credentials
from app.email_client import EmailClient
from app.main import run


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
        test_sheet_id = cls.config.database["sheet_id"]
        if not test_sheet_id:
            raise unittest.SkipTest("SHEET_ID must be configured in .env.test")
        if not cls.config.local_ia_enabled:
            raise unittest.SkipTest("LOCAL_IA_ENABLED must be true")
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

    def test_email_to_local_ia_to_sheets_and_reply(self):
        marker = uuid.uuid4().hex[:12]
        subject = f"E2E-turno-{marker}"
        body = (
            f"Paciente: E2E Paciente {marker}\n"
            "Estudio: Radiografia\n"
            "Detalle: Radiografia mano izquierda\n"
            "Clinica: E2E Clinica\n"
            "Fecha: 31/12/2099\n"
            "Hora: 23:59"
        )
        reply_subject = f"Re: {subject}"

        self._send_email(subject, body)
        received = self._wait_for_email(subject, self.config.imap["folder"])
        self.assertIsNotNone(received, "The E2E email was not received")

        test_config = replace(
            self.config,
            imap={
                **self.config.imap,
                "search": f'HEADER Subject "{subject}"',
            },
            allowed_senders=self.config.allowed_senders
            | {self.config.smtp["username"].lower()},
        )
        run(config=test_config, max_cycles=1, sleep=lambda _: None)

        processed = self._wait_for_email(subject, self.config.processed_folder)
        self.assertIsNotNone(processed, "The E2E email was not moved to processed")
        reply = self._wait_for_email(reply_subject, self.config.imap["folder"])
        self.assertIsNotNone(reply, "The success reply was not received")
        self.assertIn("agregado correctamente", reply.body)

        appointment_rows = [
            row
            for row in self.sheet.get_all_values()
            if marker in row and subject in row
        ]
        self.assertEqual(len(appointment_rows), 1)
        self.assertEqual(appointment_rows[0][0], f"E2E Paciente {marker}")
        self.assertEqual(appointment_rows[0][1], "Radiografia")
        self.assertEqual(appointment_rows[0][2], "Radiografia mano izquierda")

        email_rows = [
            row
            for row in self.email_sheet.get_all_values()
            if marker in row and subject in row
        ]
        self.assertEqual(len(email_rows), 1)
        self.assertIn(body, email_rows[0][-1])

        if os.getenv("KEEP_END_TO_END_DATA") != "1":
            self._clean_emails(subject, reply_subject)
            self._clean_sheet_rows(marker)

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
                search=f'HEADER Subject "{subject}"',
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
                        search=f'HEADER Subject "{subject}"',
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
                if marker in row
            ]
            for row_number in reversed(row_numbers):
                worksheet.delete_rows(row_number)


if __name__ == "__main__":
    unittest.main()
