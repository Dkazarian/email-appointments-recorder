import json
import os
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

import gspread

from app.appointments_sheet import AppointmentsSheet
from app.config import load_dotenv_file
from app.email_client import EmailItem
from app.models import Appointment


@unittest.skipUnless(
    os.getenv("RUN_SHEETS_INTEGRATION_TESTS") == "1",
    "Set RUN_SHEETS_INTEGRATION_TESTS=1 to use the real Google Sheet",
)
class AppointmentsSheetIntegrationTests(unittest.TestCase):
    """Integration test for the native table-backed Turnos worksheet."""

    @classmethod
    def setUpClass(cls):
        load_dotenv_file()
        credentials = cls._credentials()
        cls.spreadsheet_id = os.getenv("SHEETS_TEST_ID")
        if not cls.spreadsheet_id:
            spreadsheet_name = os.getenv("SHEETS_TEST_NAME", "Turnos-test")
            cls.spreadsheet_id = gspread.service_account_from_dict(
                credentials
            ).open(spreadsheet_name).id
        cls.sheet_name = os.getenv("SHEETS_TEST_TAB", "Turnos")
        cls.table_name = os.getenv("SHEETS_TEST_TABLE", "Turnos")
        cls.spreadsheet = gspread.service_account_from_dict(credentials).open_by_key(
            cls.spreadsheet_id
        )
        cls.sheet = cls.spreadsheet.worksheet(cls.sheet_name)
        cls.sheets = AppointmentsSheet(credentials, cls.spreadsheet_id, cls.table_name)

    @staticmethod
    def _credentials():
        raw_credentials = os.getenv("GOOGLE_CREDENTIALS")
        if not raw_credentials:
            raise unittest.SkipTest("Set GOOGLE_CREDENTIALS")

        raw_credentials = raw_credentials.strip()
        try:
            return json.loads(raw_credentials)
        except json.JSONDecodeError:
            pass

        if len(raw_credentials) < 240:
            credentials_path = Path(raw_credentials)
            if credentials_path.is_file():
                try:
                    return json.loads(credentials_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    raise unittest.SkipTest(
                        "GOOGLE_CREDENTIALS file is not valid JSON"
                    ) from error

        raise unittest.SkipTest(
            "GOOGLE_CREDENTIALS must contain service-account JSON or a valid JSON file path"
        )

    def test_appends_and_reads_a_combined_row(self):
        marker = f"codex-sheets-integration-{uuid.uuid4()}"
        email = EmailItem(
            uid=marker,
            url="https://example.test/codex-sheets-integration",
            sender="codex-integration@example.test",
            reply_to="codex-integration@example.test",
            recipients=["sheets-test@example.test"],
            subject=f"{marker} appointment",
            sent_at=datetime(2099, 12, 31, 23, 59, tzinfo=timezone.utc),
            body="Google Sheets integration test",
        )
        appointment = Appointment(
            patient_name=marker,
            study="Radiografía de prueba",
            clinic="Clínica de integración",
            date="31/12/2099",
            time="23:59:00",
        )

        try:
            self.sheets.add_appointments([(email, appointment)])
            matching_rows = [
                row for row in self.sheet.get_all_values() if marker in row
            ]

            self.assertEqual(matching_rows, [
                AppointmentsSheet.email_and_appointment_to_row(email, appointment)
            ])
        finally:
            if os.getenv("KEEP_SHEETS_INTEGRATION_ROWS") != "1":
                values = self.sheet.get_all_values()
                row_numbers = [
                    index
                    for index, row in enumerate(values, start=1)
                    if marker in row
                ]
                for row_number in reversed(row_numbers):
                    self.sheet.delete_rows(row_number)


if __name__ == "__main__":
    unittest.main()
