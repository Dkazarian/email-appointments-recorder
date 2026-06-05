from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    imap_folder: str
    imap_search: str
    ollama_base_url: str
    ollama_model: str
    google_credentials: str | None
    sheet_id: str | None
    sheet_tab: str
    mark_processed: bool
    txt_output_path: str
    poll_interval_minutes: int
    processed_folder: str
    failed_folder: str
    prompt_file: str
    ai_provider: str


def load_settings() -> Settings:
    load_dotenv_file()

    return Settings(
        imap_host=_required("IMAP_HOST"),
        imap_port=int(os.getenv("IMAP_PORT", "993")),
        imap_user=_required("IMAP_USER"),
        imap_password=_required("IMAP_PASSWORD"),
        imap_folder=os.getenv("IMAP_FOLDER", "INBOX"),
        imap_search=os.getenv("IMAP_SEARCH", "UNSEEN"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        google_credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        sheet_id=os.getenv("SHEET_ID"),
        sheet_tab=os.getenv("SHEET_TAB", "Solicitudes"),
        mark_processed=os.getenv("MARK_PROCESSED", "false").lower() == "true",
        txt_output_path=os.getenv("TXT_OUTPUT_PATH", "work/processed_mails.txt"),
        poll_interval_minutes=int(os.getenv("POLL_INTERVAL_MINUTES", "15")),
        processed_folder=os.getenv("MAIL_PROCESSED_FOLDER", "Procesados"),
        failed_folder=os.getenv("MAIL_FAILED_FOLDER", "Fallidos"),
        prompt_file=os.getenv("PROMPT_FILE", "prompts/system_prompt.txt"),
        ai_provider=os.getenv("AI_PROVIDER", "ollama"),
    )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


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
