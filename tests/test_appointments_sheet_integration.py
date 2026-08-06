import os
import unittest
import uuid
from datetime import datetime, timezone

from app.appointments_sheet import AppointmentsSheet
from app.config import load_config, load_dotenv_file, load_google_credentials
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
        cls.config = load_config()
        raw_credentials = os.getenv("GOOGLE_CREDENTIALS")
        if not raw_credentials:
            raise unittest.SkipTest("Set GOOGLE_CREDENTIALS")
        try:
            credentials = load_google_credentials(raw_credentials)
        except ValueError as error:
            raise unittest.SkipTest(str(error)) from error
        cls.spreadsheet_id = os.getenv("SHEETS_TEST_ID") or cls.config.database["sheet_id"]
        if not cls.spreadsheet_id:
            raise unittest.SkipTest("Set SHEETS_TEST_ID or SHEET_ID")
        cls.table_name = os.getenv("SHEETS_TEST_TABLE", "Turnos")
        cls.email_table_name = os.getenv("SHEETS_TEST_EMAIL_TAB", "Correos")
        cls.sheets = AppointmentsSheet(
            credentials,
            cls.spreadsheet_id,
            cls.table_name,
            cls.email_table_name,
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
            clinic_or_professional="Clínica de integración",
            date="31/12/2099",
            time="23:59:00",
        )

        try:
            self.sheets.add_appointments([(email, appointment)])
            matching_rows = [row for row in self.sheets.get_rows() if marker in row]
            matching_email_rows = [
                row
                for row in self.sheets.get_rows(self.email_table_name)
                if marker in row
            ]

            self.assertEqual(matching_rows, [
                AppointmentsSheet.email_and_appointment_to_row(
                    email,
                    appointment,
                )
            ])
            self.assertEqual(matching_email_rows, [
                AppointmentsSheet.email_to_row(email)
            ])
        finally:
            self._cleanup_marker(marker)

    def test_multiple_appointments_and_duplicate_prevention(self):
        marker = f"codex-sheets-multi-{uuid.uuid4()}"
        email = EmailItem(
            uid=marker,
            url="https://example.test/codex-sheets-multi",
            sender="codex-integration@example.test",
            reply_to="codex-integration@example.test",
            recipients=["sheets-test@example.test"],
            subject=f"{marker} appointment",
            sent_at=datetime(2099, 12, 31, 23, 59, tzinfo=timezone.utc),
            body="Google Sheets multiple appointment integration test",
        )
        appointments = [
            Appointment(patient_name=marker, study="Study one", date="31/12/2099"),
            Appointment(patient_name=marker, study="Study two", date="31/12/2099"),
        ]

        try:
            payload = [(email, appointment) for appointment in appointments]
            self.sheets.add_appointments(payload)
            self.sheets.add_appointments(payload)

            matching_rows = [row for row in self.sheets.get_rows() if marker in row]
            matching_email_rows = [
                row
                for row in self.sheets.get_rows(self.email_table_name)
                if marker in row
            ]
            self.assertEqual(len(matching_rows), 2)
            self.assertEqual(len(matching_email_rows), 1)
        finally:
            self._cleanup_marker(marker)

    def _cleanup_marker(self, marker):
        if os.getenv("KEEP_SHEETS_INTEGRATION_ROWS") == "1":
            return
        for table_name in (self.table_name, self.email_table_name):
            rows = self.sheets.get_rows(table_name)
            row_numbers = [
                index for index, row in enumerate(rows, start=1) if marker in row
            ]
            self.sheets.delete_rows(row_numbers, table_name)


if __name__ == "__main__":
    unittest.main()
