from dataclasses import dataclass
import json
import os
from pathlib import Path


def _get_env(*names: str, default: str | None = None) -> str | None:
    """Read the first configured variable, supporting the previous names."""
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value
    return default


@dataclass(frozen=True)
class Config:
    imap: object
    smtp: object
    processed_folder: str
    failed_folder: str
    allowed_senders: set[str]
    google_ai_studio_api_key: str
    google_ai_studio_model: str
    openrouter_api_key: str | None
    open_router_model: str | None
    local_ai_enabled: bool
    local_ai_base_url: str
    local_ai_model: str
    local_ai_timeout_seconds: int
    interval_minutes: int
    mail_web_base_url: str
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
            "credentials": os.getenv("GOOGLE_CREDENTIALS"),
            "sheet_id": os.getenv("SHEET_ID"),
            "table_name": os.getenv("SHEET_TABLE", "Turnos"),
            "email_table_name": os.getenv("SHEET_EMAIL_TABLE", "Correos"),
            "sheet_tab": os.getenv("SHEET_TAB", "Turnos"),
        },
        google_ai_studio_api_key=_get_env(
            "GOOGLE_AI_STUDIO_API_KEY", "GOOGLE_STUDIO_AI_API_KEY", "GEMINI_IA_API_KEY"
        ),
        google_ai_studio_model=_get_env(
            "GOOGLE_AI_STUDIO_MODEL",
            "GOOGLE_STUDIO_AI_MODEL",
            "GEMINI_IA_MODEL",
            default="gemini-2.0-flash",
        ),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        open_router_model=os.getenv("OPEN_ROUTER_MODEL"),
        local_ai_enabled=_get_env(
            "LOCAL_AI_ENABLED", "LOCAL_IA_ENABLED", default="false"
        ).lower()
        == "true",
        local_ai_base_url=_get_env(
            "LOCAL_AI_BASE_URL", "LOCAL_IA_BASE_URL", default="http://localhost:1234/v1"
        ),
        local_ai_model=_get_env(
            "LOCAL_AI_MODEL", "LOCAL_IA_MODEL", default="google_gemma-3-4b-it"
        ),
        local_ai_timeout_seconds=int(
            _get_env("LOCAL_AI_TIMEOUT_SECONDS", "LOCAL_IA_TIMEOUT_SECONDS", default="300")
        ),
        interval_minutes=int(os.getenv("INTERVAL_MINUTES")),
        mail_web_base_url=os.getenv(
            "MAIL_WEB_BASE_URL", "https://mail.google.com/mail/u/0"
        ),
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


def load_google_credentials(raw_credentials: str | None) -> dict:
    if not raw_credentials:
        raise ValueError("GOOGLE_CREDENTIALS is not configured")

    raw_credentials = raw_credentials.strip()
    try:
        return json.loads(raw_credentials)
    except json.JSONDecodeError:
        pass

    if len(raw_credentials) < 240:
        credentials_path = Path(raw_credentials)
        if credentials_path.is_file():
            return json.loads(credentials_path.read_text(encoding="utf-8"))

    raise ValueError(
        "GOOGLE_CREDENTIALS must contain service-account JSON or a valid JSON file path"
    )
