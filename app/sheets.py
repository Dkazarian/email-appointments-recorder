from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import Settings
from .mail_client import MailItem
from .model import SheetAction


COLUMNS = [
    "concepto",
    "monto",
    "estado",
    "fecha_vencimiento",
    "fecha_pago",
]
HEADER = ["Concepto", "Monto", "Estado", "Fecha de vencimiento", "Fecha de pago"]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsSink:
    def __init__(self, settings: Settings):
        if not settings.sheet_id:
            raise RuntimeError("SHEET_ID es obligatorio para escribir en Google Sheets.")

        self.settings = settings
        credentials = load_oauth_credentials(settings)
        self.service = build("sheets", "v4", credentials=credentials)
        self.ensure_header()

    def apply(self, mail: MailItem, action: SheetAction) -> str:
        if action.action == "append_row":
            return self.append_row(action.row)
        raise ValueError(f"Accion no soportada: {action.action}")

    def append_row(self, row: dict) -> str:
        row = normalize_row(row)
        values = [[_cell(row.get(column)) for column in COLUMNS]]
        self.service.spreadsheets().values().append(
            spreadsheetId=self.settings.sheet_id,
            range=f"{self.settings.sheet_tab}!A:E",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
        return "fila agregada"

    def ensure_header(self) -> None:
        self.service.spreadsheets().values().update(
            spreadsheetId=self.settings.sheet_id,
            range=f"{self.settings.sheet_tab}!A1:E1",
            valueInputOption="USER_ENTERED",
            body={"values": [HEADER]},
        ).execute()

SheetsClient = SheetsSink


def load_oauth_credentials(settings: Settings):
    token_path = Path(settings.google_oauth_token)
    client_secret_path = Path(settings.google_oauth_client_secret)
    credentials = None

    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        if not client_secret_path.exists():
            raise RuntimeError(f"No se encontro el archivo OAuth de Google: {client_secret_path}")
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
        credentials = flow.run_local_server(port=0)

    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def normalize_row(row: dict) -> dict:
    normalized = dict(row)
    fecha_pago = str(normalized.get("fecha_pago") or "").strip()
    estado = str(normalized.get("estado") or "").strip().lower()
    if estado not in {"pagado", "pendiente"}:
        normalized["estado"] = "pagado" if fecha_pago else "pendiente"
    return normalized


def _cell(value) -> str:
    if value is None:
        return ""
    return str(value)
