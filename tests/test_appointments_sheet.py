import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.email_client import EmailItem
from app.models import Appointment
from app.appointments_sheet import AppointmentsSheet, SheetsError, headers


class AppointmentsSheetTests(unittest.TestCase):
    def setUp(self):
        self.email = EmailItem(
            uid="42",
            url="https://mail.google.com/mail/u/0/#search/example",
            sender="secretaria@gmail.com",
            reply_to="secretaria@gmail.com",
            recipients=["clinica@example.com", "planilla@example.com"],
            subject="Turno para Ernesto",
            sent_at=datetime(2025, 3, 24, 15, 55, tzinfo=timezone.utc),
            body="Radiografia 24/3 15:55 para Ernesto",
        )
        self.appointment = Appointment(
            patient_name="Ernesto",
            study="Radiografia",
            clinic="Clinica Rosa",
            date="24/3",
            time="15:55",
        )

    @patch("app.appointments_sheet.gspread.service_account_from_dict")
    def test_initializes_gspread_client_and_worksheet(self, service_account):
        spreadsheet = service_account.return_value.open_by_key.return_value

        sheets = AppointmentsSheet({"client_email": "test@example.com"}, "spreadsheet-id", "Turnos")

        service_account.assert_called_once_with({"client_email": "test@example.com"})
        service_account.return_value.open_by_key.assert_called_once_with("spreadsheet-id")
        spreadsheet.worksheet.assert_called_once_with("Turnos")
        self.assertIs(sheets.sheet, spreadsheet.worksheet.return_value)

    @patch("app.appointments_sheet.gspread.service_account_from_dict")
    def test_appends_rows_with_user_entered_values(self, service_account):
        sheets = AppointmentsSheet({}, "spreadsheet-id", "Turnos")
        rows = [["42", "value"]]

        sheets.append_rows_to_table(rows)

        sheets.sheet.append_rows.assert_called_once_with(rows, value_input_option="USER_ENTERED")

    @patch("app.appointments_sheet.gspread.service_account_from_dict")
    def test_wraps_gspread_errors(self, service_account):
        sheets = AppointmentsSheet({}, "spreadsheet-id", "Turnos")
        sheets.sheet.append_rows.side_effect = RuntimeError("quota exceeded")

        with self.assertRaisesRegex(SheetsError, "quota exceeded"):
            sheets.append_rows_to_table([["42"]])

    @patch("app.appointments_sheet.gspread.service_account_from_dict")
    def test_add_appointments_converts_and_appends_each_appointment(self, service_account):
        sheets = AppointmentsSheet({}, "spreadsheet-id", "Turnos")
        second_appointment = self.appointment.model_copy(update={"patient_name": "Ana"})

        sheets.add_appointments([
            (self.email, self.appointment),
            (self.email, second_appointment),
        ])

        rows = sheets.sheet.append_rows.call_args.args[0]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][-1], "pendiente")
        self.assertEqual(rows[1][6], "Ana")

    def test_headers_and_row_match(self):
        row = AppointmentsSheet.email_and_appointment_to_row(self.email, self.appointment)

        self.assertEqual(len(row), len(headers))
        self.assertEqual(row, [
            "42",
            "2025-03-24T15:55:00+00:00",
            "Turno para Ernesto",
            "secretaria@gmail.com",
            "clinica@example.com, planilla@example.com",
            "https://mail.google.com/mail/u/0/#search/example",
            "Ernesto",
            "Radiografia",
            "Clinica Rosa",
            "24/3 15:55",
            "pendiente",
        ])


if __name__ == "__main__":
    unittest.main()
