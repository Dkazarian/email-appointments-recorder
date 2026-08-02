"""Seed a Google Sheet with deterministic appointment data for manual testing."""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gspread

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.appointments_sheet import AppointmentsSheet, email_headers, headers
from app.config import load_dotenv_file
from app.email_client import EmailItem
from app.models import Appointment


PATIENTS = [
    "Ana García",
    "Bruno López",
    "Carla Martínez",
    "Diego Fernández",
    "Elena Rodríguez",
    "Fabián Gómez",
    "Gabriela Díaz",
    "Hugo Sosa",
    "Irene Romero",
    "Julián Torres",
]

STUDIES = [
    "Radiografía",
    "Ecografía",
    "Tomografía",
    "Resonancia magnética",
    "Laboratorio",
]

CLINICS = [
    "Clínica Central",
    "Sanatorio Norte",
    "Centro Médico del Sur",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--spreadsheet-name", default="Turnos-test")
    parser.add_argument("--spreadsheet-id")
    parser.add_argument("--sheet", default="Turnos")
    parser.add_argument("--table-name", default=os.getenv("SHEET_TABLE", "Turnos"))
    parser.add_argument(
        "--email-table-name",
        default=os.getenv("SHEET_EMAIL_TABLE", "Correos"),
    )
    return parser.parse_args()


def credentials_from_environment() -> dict:
    load_dotenv_file()
    raw_credentials = os.getenv("GOOGLE_CREDENTIALS")
    if not raw_credentials:
        raise RuntimeError("GOOGLE_CREDENTIALS is not configured")

    raw_credentials = raw_credentials.strip()
    try:
        return json.loads(raw_credentials)
    except json.JSONDecodeError:
        pass

    if len(raw_credentials) < 240:
        credentials_path = Path(raw_credentials)
        if credentials_path.is_file():
            return json.loads(credentials_path.read_text(encoding="utf-8"))

    raise RuntimeError(
        "GOOGLE_CREDENTIALS must contain service-account JSON or a valid JSON file path"
    )


def seed_records(count: int) -> list[tuple[EmailItem, Appointment]]:
    if count < 1:
        raise ValueError("count must be positive")

    appointments_by_email: dict[int, list[Appointment]] = {}
    sent_at_by_email: dict[int, datetime] = {}
    base_date = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)
    for index in range(1, count + 1):
        # Include a few multi-appointment emails to exercise the one-to-many
        # relationship between source emails and rows in the appointments table.
        email_number = (
            1 if index <= 3 else
            2 if 10 <= index <= 12 else
            index
        )
        sent_at = base_date + timedelta(hours=email_number)
        appointment_date = sent_at + timedelta(days=7 + index % 14)
        appointment = Appointment(
            patient_name=PATIENTS[(index - 1) % len(PATIENTS)],
            study=STUDIES[(index - 1) % len(STUDIES)],
            clinic=CLINICS[(index - 1) % len(CLINICS)],
            date=appointment_date.strftime("%d/%m/%Y"),
            time=appointment_date.strftime("%H:%M:%S"),
        )
        appointments_by_email.setdefault(email_number, []).append(appointment)
        sent_at_by_email[email_number] = sent_at

    records = []
    for email_number, appointments in appointments_by_email.items():
        uid = f"seed-appointment-email-{email_number:03d}"
        appointment_lines = "\n\n".join(
            "\n".join(
                [
                    f"Paciente: {appointment.patient_name}",
                    f"Estudio: {appointment.study}",
                    f"Clínica: {appointment.clinic}",
                    f"Fecha del turno: {appointment.date}",
                    f"Hora del turno: {appointment.time}",
                ]
            )
            for appointment in appointments
        )
        email = EmailItem(
            uid=uid,
            url=f"https://example.test/seed/{uid}",
            sender="seed@example.test",
            reply_to="seed@example.test",
            recipients=["planilla@example.test"],
            subject=f"Turnos de prueba {email_number:03d}",
            sent_at=sent_at_by_email[email_number],
            body=(
                "Correo generado para poblar la planilla de pruebas.\n\n"
                f"{appointment_lines}"
            ),
        )
        records.extend((email, appointment) for appointment in appointments)
    return records


def format_date_columns(spreadsheet, worksheet_id: int, email_worksheet_id: int) -> None:
    spreadsheet.batch_update(
        {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": worksheet_id,
                            "startRowIndex": 1,
                            "startColumnIndex": 3,
                            "endColumnIndex": 4,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "DATE",
                                    "pattern": "dd/MM/yyyy",
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": worksheet_id,
                            "startRowIndex": 1,
                            "startColumnIndex": 4,
                            "endColumnIndex": 5,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "TIME",
                                    "pattern": "HH:mm:ss",
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": worksheet_id,
                            "startRowIndex": 1,
                            "startColumnIndex": 8,
                            "endColumnIndex": 9,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "DATE_TIME",
                                    "pattern": "dd/MM/yyyy HH:mm:ss",
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": email_worksheet_id,
                            "startRowIndex": 1,
                            "startColumnIndex": 1,
                            "endColumnIndex": 2,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "DATE_TIME",
                                    "pattern": "dd/MM/yyyy HH:mm:ss",
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                },
            ]
        }
    )


def main() -> None:
    args = parse_args()
    credentials = credentials_from_environment()
    client = gspread.service_account_from_dict(credentials)
    spreadsheet_id = args.spreadsheet_id or client.open(args.spreadsheet_name).id
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(args.sheet)
    email_worksheet = spreadsheet.worksheet(args.email_table_name)
    sheets = AppointmentsSheet(
        credentials,
        spreadsheet_id,
        args.table_name,
        args.email_table_name,
    )

    if worksheet.row_values(1) != headers:
        worksheet.update(values=[headers], range_name="A1:M1")
    if email_worksheet.row_values(1) != email_headers:
        email_worksheet.update(values=[email_headers], range_name="A1:G1")

    records = seed_records(args.count)
    existing_ids = {
        value
        for row in worksheet.get_all_values()
        for value in row
        if value.startswith("seed-appointment-email-")
    }
    records_to_add = [
        (email, appointment)
        for email, appointment in records
        if email.uid not in existing_ids
    ]

    if records_to_add:
        sheets.add_appointments(records_to_add)

    # Apply formatting after insertion so newly added rows do not inherit the
    # sheet's general format and display date/time serial numbers.
    format_date_columns(spreadsheet, worksheet.id, email_worksheet.id)

    print(
        f"Spreadsheet: {spreadsheet_id}\n"
        f"Sheet: {args.sheet}\n"
        f"Requested: {len(records)}\n"
        f"Added: {len(records_to_add)}\n"
        f"Skipped existing: {len(records) - len(records_to_add)}"
    )


if __name__ == "__main__":
    main()
