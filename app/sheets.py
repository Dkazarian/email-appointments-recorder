from google.oauth2 import service_account
from googleapiclient.discovery import build

from .config import Settings
from .mail_client import MailItem
from .model import SheetAction


COLUMNS = [
    "fecha",
    "remitente",
    "estado",
    "descripcion",
    "categoria",
    "monto",
    "vencimiento",
    "notas",
    "mail_id",
]


class SheetsSink:
    def __init__(self, settings: Settings):
        if not settings.google_credentials or not settings.sheet_id:
            raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS y SHEET_ID son obligatorios para escribir en Google Sheets.")

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_credentials,
            scopes=scopes,
        )
        self.settings = settings
        self.service = build("sheets", "v4", credentials=credentials)

    def apply(self, mail: MailItem, action: SheetAction) -> str:
        if action.action == "ignore":
            return "ignored"
        if action.action == "needs_review":
            action = _review_action(action)
        if action.action == "append_row":
            return self.append_row(action.row)
        if action.action == "update_row":
            if not action.match_mail_id:
                return self.append_row({**action.row, "notas": _append_note(action.row.get("notas"), "Sin match_mail_id; agregado para revision.")})
            row_number = self.find_row_by_mail_id(action.match_mail_id)
            if row_number is None:
                return self.append_row({**action.row, "notas": _append_note(action.row.get("notas"), "No se encontro mail_id; agregado para revision.")})
            self.update_row(row_number, action.row)
            return f"fila {row_number} actualizada"
        raise ValueError(f"Accion no soportada: {action.action}")

    def append_row(self, row: dict) -> str:
        values = [[_cell(row.get(column)) for column in COLUMNS]]
        self.service.spreadsheets().values().append(
            spreadsheetId=self.settings.sheet_id,
            range=f"{self.settings.sheet_tab}!A:I",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
        return "fila agregada"

    def update_row(self, row_number: int, row: dict) -> None:
        existing = self.get_row(row_number)
        merged = {column: existing.get(column, "") for column in COLUMNS}
        for key, value in row.items():
            if key in COLUMNS and value not in (None, ""):
                merged[key] = value
        values = [[_cell(merged.get(column)) for column in COLUMNS]]
        self.service.spreadsheets().values().update(
            spreadsheetId=self.settings.sheet_id,
            range=f"{self.settings.sheet_tab}!A{row_number}:I{row_number}",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()

    def find_row_by_mail_id(self, mail_id: str) -> int | None:
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.settings.sheet_id,
            range=f"{self.settings.sheet_tab}!A:I",
        ).execute()
        rows = result.get("values", [])
        for index, row in enumerate(rows[1:], start=2):
            if len(row) >= 9 and row[8] == mail_id:
                return index
        return None

    def get_row(self, row_number: int) -> dict[str, str]:
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.settings.sheet_id,
            range=f"{self.settings.sheet_tab}!A{row_number}:I{row_number}",
        ).execute()
        values = result.get("values", [[]])[0]
        return {column: values[index] if index < len(values) else "" for index, column in enumerate(COLUMNS)}


SheetsClient = SheetsSink


def _review_action(action: SheetAction) -> SheetAction:
    row = dict(action.row)
    row["estado"] = row.get("estado") or "requiere_revision"
    row["notas"] = _append_note(row.get("notas"), action.reason)
    return SheetAction(action="append_row", reason=action.reason, row=row)


def _append_note(existing, note: str) -> str:
    parts = [str(existing or "").strip(), str(note or "").strip()]
    return " | ".join(part for part in parts if part)


def _cell(value) -> str:
    if value is None:
        return ""
    return str(value)
