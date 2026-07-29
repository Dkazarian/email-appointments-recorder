from dataclasses import dataclass
import os
from pathlib import Path

@dataclass(frozen=True)
class Config:
    imap: object
    smtp: object
    processed_folder: str
    failed_folder: str
    api_key: str
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
        database= {
            "client_secret": Path(os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")),
            "token": Path(os.getenv("GOOGLE_OAUTH_TOKEN")),
            "sheet_id": os.getenv("SHEET_ID"),
            "sheet_tab": os.getenv("SHEET_TAB")
        },
        api_key=os.getenv("API_KEY"),
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
