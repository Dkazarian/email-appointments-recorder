import gspread
from app.email_client import EmailItem
from app.models import Appointment
from typing import Any

class SheetsError(Exception):
    pass

headers = [
    "id",
    "fecha del mail",
    "asunto",
    "remitente",
    "destinatarios",
    "url",
    "paciente",
    "estudio",
    "clinica",
    "fecha del turno",
    "estado",
]

class AppointmentsSheet:
    def __init__(self, credentials: dict[str, Any], spreadsheet_id: str, sheet_name: str) -> None:
        self.gc = gspread.service_account_from_dict(credentials)
        self.spreadsheet = self.gc.open_by_key(spreadsheet_id)
        self.sheet = self.spreadsheet.worksheet(sheet_name)

    def add_appointments(self, appointments: list[tuple[EmailItem, Appointment]]) -> None:
        self.append_rows_to_table([self.email_and_appointment_to_row(email, appointment) for email, appointment in appointments ])

    def append_rows_to_table(self, rows_data: list[list[str]]) -> None:
        try:
            self.sheet.append_rows(rows_data, value_input_option="USER_ENTERED")
        except Exception as e:
            raise SheetsError(f"Error al agregar filas a la hoja de cálculo: {e}")
        
    @staticmethod
    def email_and_appointment_to_row(
        email: EmailItem,
        appointment: Appointment,
        status: str = "pendiente",
    ) -> list[str]:
        appointment_date = " ".join(
            value for value in (appointment.date, appointment.time) if value
        )

        return [
            email.uid,
            email.sent_at.isoformat() if email.sent_at else "",
            email.subject,
            email.sender,
            ", ".join(email.recipients),
            email.url or "",
            appointment.patient_name or "",
            appointment.study or "",
            appointment.clinic or "",
            appointment_date,
            status,
        ]
