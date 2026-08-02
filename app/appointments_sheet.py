from datetime import datetime
from typing import Any

import gspread
from app.email_client import EmailItem
from app.models import Appointment


class SheetsError(Exception):
    pass

headers = [
    "Paciente",
    "Estudio",
    "Clínica",
    "Fecha del turno",
    "Hora del turno",
    "Estado",
    "Verificado",
    "UID",
    "Fecha del mail",
    "Asunto",
    "Remitente",
    "Destinatarios",
    "URL",
]

email_headers = [
    "UID",
    "Fecha del mail",
    "Asunto",
    "Remitente",
    "Destinatarios",
    "URL",
    "Texto del mail",
]

class AppointmentsSheet:
    def __init__(
        self,
        credentials: dict[str, Any],
        spreadsheet_id: str,
        table_name: str,
        email_table_name: str = "Correos",
    ) -> None:
        self.gc = gspread.service_account_from_dict(credentials)
        self.spreadsheet = self.gc.open_by_key(spreadsheet_id)
        self.table_name = table_name
        self.email_table_name = email_table_name

    def add_appointments(self, appointments: list[tuple[EmailItem, Appointment]]) -> None:
        if not appointments:
            return

        unique_emails = dict((email.uid, email) for email, _ in appointments)
        self._append_rows(
            self.email_table_name,
            [self.email_to_row(email) for email in unique_emails.values()],
        )
        self._append_rows(
            self.table_name,
            [
                self.email_and_appointment_to_row(email, appointment)
                for email, appointment in appointments
            ],
        )

    def append_rows_to_table(self, rows_data: list[list[str]]) -> None:
        self._append_rows(self.table_name, rows_data)

    def _append_rows(
        self,
        table_name: str,
        rows_data: list[list[str]],
        value_input_option: str = "RAW",
    ) -> None:
        try:
            self.spreadsheet.values_append(
                range=table_name,
                params={
                    "valueInputOption": value_input_option,
                    "insertDataOption": "INSERT_ROWS",
                },
                body={"values": rows_data},
            )
        except Exception as error:
            raise SheetsError(f"Error al agregar filas a la hoja de cálculo: {error}")

    @staticmethod
    def _appointment_date(appointment: Appointment) -> str:
        date = appointment.date or ""
        for date_format in ("%d/%m/%Y", "%d/%m/%y"):
            try:
                date = datetime.strptime(date, date_format).strftime("%d/%m/%Y")
                break
            except ValueError:
                pass

        return date

    @staticmethod
    def _appointment_time(appointment: Appointment) -> str:
        time = appointment.time or ""
        if time and time.count(":") == 1:
            time = f"{time}:00"
        return time

    @staticmethod
    def email_and_appointment_to_row(
        email: EmailItem,
        appointment: Appointment,
        status: str = "PENDIENTE",
    ) -> list[str]:
        return [
            appointment.patient_name or "",
            appointment.study or "",
            appointment.clinic or "",
            AppointmentsSheet._appointment_date(appointment),
            AppointmentsSheet._appointment_time(appointment),
            status,
            "",
            email.uid,
            email.sent_at.strftime("%d/%m/%Y %H:%M:%S") if email.sent_at else "",
            email.subject,
            email.sender,
            ", ".join(email.recipients),
            email.url or "",
        ]

    @staticmethod
    def email_to_row(email: EmailItem) -> list[str]:
        return [
            email.uid,
            email.sent_at.strftime("%d/%m/%Y %H:%M:%S") if email.sent_at else "",
            email.subject,
            email.sender,
            ", ".join(email.recipients),
            email.url or "",
            email.body,
        ]
