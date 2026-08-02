from dataclasses import dataclass
import os
from pathlib import Path

@dataclass(frozen=True)
class Config:
    imap: object
    smtp: object
    processed_folder: str
    failed_folder: str
    allowed_senders: set[str]
    gemini_ia_api_key: str
    gemini_ia_model: str
    openrouter_api_key: str | None
    open_router_model: str | None
    local_ia_enabled: bool
    local_ia_base_url: str
    local_ia_model: str
    local_ia_timeout_seconds: int
    interval_minutes: int
    database: object

def load_config() -> Config:
    load_dotenv_file()

    return Config(
        imap= {
            "host": os.getenv("IMAP_HOST"),
            "port": int(os.getenv("IMAP_PORT")),
            "username": os.getenv("IMAP_USER"),
            "password": os.getenv("IMAP_PASSWORD"),
            "folder": os.getenv("IMAP_FOLDER"),
            "search": os.getenv("IMAP_SEARCH")
        },
        smtp= {
            "host": os.getenv("SMTP_HOST"),
            "port": int(os.getenv("SMTP_PORT")),
            "username": os.getenv("SMTP_USER"),
            "password": os.getenv("SMTP_PASSWORD")
        },
        processed_folder= os.getenv("MAIL_PROCESSED_FOLDER"),
        failed_folder= os.getenv("MAIL_FAILED_FOLDER"),
        allowed_senders={
            sender.strip().lower()
            for sender in os.getenv("ALLOWED_SENDERS", "").split(",")
            if sender.strip()
        },
        database= {
            "credentials": Path(os.getenv("GOOGLE_CREDENTIALS")),
            "sheet_id": os.getenv("SHEET_ID"),
            "table_name": os.getenv("SHEET_TABLE", "Turnos"),
            "email_table_name": os.getenv("SHEET_EMAIL_TABLE", "Correos"),
            "sheet_tab": os.getenv("SHEET_TAB", "Turnos"),
        },
        gemini_ia_api_key=os.getenv("GEMINI_IA_API_KEY"),
        gemini_ia_model=os.getenv("GEMINI_IA_MODEL", "gemini-2.0-flash"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        open_router_model=os.getenv("OPEN_ROUTER_MODEL"),
        local_ia_enabled=os.getenv("LOCAL_IA_ENABLED", "false").lower() == "true",
        local_ia_base_url=os.getenv("LOCAL_IA_BASE_URL", "http://localhost:1234/v1"),
        local_ia_model=os.getenv("LOCAL_IA_MODEL", "google_gemma-3-4b-it"),
        local_ia_timeout_seconds=int(os.getenv("LOCAL_IA_TIMEOUT_SECONDS", "300")),
        interval_minutes=int(os.getenv("INTERVAL_MINUTES"))
    )


def load_dotenv_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
