import json
import time

from .appointments_extractor import AppointmentsExtractor
from .appointments_sheet import AppointmentsSheet
from .config import load_config
from .email_client import EmailClient
from .gemini_ia_client import GeminiIAClient
from .logger import Logger


def main() -> None:
    config = load_config()
    credentials = json.loads(
        config.database["credentials"].read_text(encoding="utf-8")
    )
    extractor = AppointmentsExtractor(GeminiIAClient(config.api_key))
    sheets = AppointmentsSheet(
        credentials,
        config.database["sheet_id"],
        config.database["sheet_tab"],
    )
    logger = Logger()

    with EmailClient(
        config.imap,
        config.smtp,
        config.processed_folder,
        config.failed_folder,
    ) as email_client:
        while True:
            try:
                emails = email_client.fetch()
                extracted, failed = extractor.parse_all(emails)
                sheets.add_appointments(
                    [(item.mail, item.appointment) for item in extracted]
                )

                for item in extracted:
                    email_client.reply_success(item.mail, item.appointment)
                    email_client.mark_completed(item.mail)

                for item in failed:
                    logger.log_error(f"{item.mail.uid}: {item.error}")
                    email_client.reply_failed(item.mail, item.error)
                    email_client.mark_failed(item.mail)
            except Exception as error:
                logger.log_error(str(error))

            time.sleep(config.interval_minutes * 60)
