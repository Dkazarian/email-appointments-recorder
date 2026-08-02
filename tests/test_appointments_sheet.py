import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.appointments_sheet import AppointmentsSheet, SheetsError, email_headers, headers
from app.email_client import EmailItem
from app.models import Appointment


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
            body="Radiografia 24/3 15:55",
        )
        self.appointment = Appointment(
            patient_name="Ernesto",
            study="Radiografia",
            study_detail="Radiografia mano izquierda",
            clinic="Clinica Rosa",
            date="24/03/2025",
            time="15:55",
        )

    @patch("app.appointments_sheet.gspread.service_account_from_dict")
    def test_initializes_with_native_table_name(self, service_account):
        sheets = AppointmentsSheet({}, "spreadsheet-id", "Turnos")

        service_account.assert_called_once_with({})
        service_account.return_value.open_by_key.assert_called_once_with("spreadsheet-id")
        self.assertEqual(sheets.table_name, "Turnos")
        self.assertEqual(sheets.email_table_name, "Correos")

    @patch("app.appointments_sheet.gspread.service_account_from_dict")
    def test_appends_rows_to_the_native_table(self, service_account):
        sheets = AppointmentsSheet({}, "spreadsheet-id", "Turnos")
        rows = [["Ernesto", "Radiografia"]]

        sheets.append_rows_to_table(rows)

        sheets.spreadsheet.values_append.assert_called_once_with(
            range="Turnos",
            params={
                "valueInputOption": "RAW",
                "insertDataOption": "INSERT_ROWS",
            },
            body={"values": rows},
        )

    @patch("app.appointments_sheet.gspread.service_account_from_dict")
    def test_wraps_gspread_errors(self, service_account):
        sheets = AppointmentsSheet({}, "spreadsheet-id", "Turnos")
        sheets.spreadsheet.values_append.side_effect = RuntimeError("quota exceeded")

        with self.assertRaisesRegex(SheetsError, "quota exceeded"):
            sheets.append_rows_to_table([["Ernesto"]])

    @patch("app.appointments_sheet.gspread.service_account_from_dict")
    def test_does_not_append_duplicate_email_and_appointment_rows(self, service_account):
        sheets = AppointmentsSheet({}, "spreadsheet-id", "Turnos")
        existing_email_row = sheets.email_to_row(self.email)
        existing_appointment_row = sheets.email_and_appointment_to_row(
            self.email, self.appointment
        )
        sheets.spreadsheet.worksheet.return_value.get_all_values.side_effect = [
            [email_headers, existing_email_row],
            [headers, existing_appointment_row],
        ]

        sheets.add_appointments([(self.email, self.appointment)])

        sheets.spreadsheet.values_append.assert_not_called()

    @patch("app.appointments_sheet.gspread.service_account_from_dict")
    def test_add_appointments_appends_one_combined_row_per_appointment(
        self, service_account
    ):
        sheets = AppointmentsSheet({}, "spreadsheet-id", "Turnos")
        second_appointment = self.appointment.model_copy(update={"patient_name": "Ana"})

        sheets.add_appointments([
            (self.email, self.appointment),
            (self.email, second_appointment),
        ])

        email_call, appointments_call = sheets.spreadsheet.values_append.call_args_list
        email_rows = email_call.kwargs["body"]["values"]
        rows = appointments_call.kwargs["body"]["values"]
        self.assertEqual(email_call.kwargs["range"], "Correos")
        self.assertEqual(len(email_rows), 1)
        self.assertEqual(len(email_rows[0]), len(email_headers))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]), len(headers))
        self.assertEqual(rows[0][0], "Ernesto")
        self.assertEqual(rows[1][0], "Ana")
        self.assertEqual(rows[0][5], "15:55:00")
        self.assertEqual(rows[0][6], "PENDIENTE")
        self.assertEqual(rows[0][7], "")
        self.assertEqual(rows[0][8], "42")

    def test_headers_and_row_match(self):
        row = AppointmentsSheet.email_and_appointment_to_row(
            self.email, self.appointment
        )

        self.assertEqual(len(row), len(headers))
        self.assertEqual(row, [
            "Ernesto",
            "Radiografia",
            "Radiografia mano izquierda",
            "Clinica Rosa",
            "24/03/2025",
            "15:55:00",
            "PENDIENTE",
            "",
            "42",
            "24/03/2025 15:55:00",
            "Turno para Ernesto",
            "secretaria@gmail.com",
            "clinica@example.com, planilla@example.com",
            "https://mail.google.com/mail/u/0/#search/example",
        ])

        self.assertEqual(AppointmentsSheet.email_to_row(self.email), [
            "42",
            "24/03/2025 15:55:00",
            "Turno para Ernesto",
            "secretaria@gmail.com",
            "clinica@example.com, planilla@example.com",
            "https://mail.google.com/mail/u/0/#search/example",
            "Radiografia 24/3 15:55",
        ])


if __name__ == "__main__":
    unittest.main()
