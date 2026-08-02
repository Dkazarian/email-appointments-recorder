import json
import time
from collections.abc import Callable
from typing import Any

from google.genai.errors import ServerError

from .appointments_extractor import AppointmentsExtractor
from .appointments_sheet import AppointmentsSheet
from .config import load_config
from .email_client import EmailClient
from .ia_clients import GeminiIAClient, LocalIAClient
from .logger import Logger
from .ia_clients import OpenRouterIAClient


def process_batch(email_client, extractor, sheets, logger) -> None:
    """Process one batch of emails."""
    emails = email_client.fetch()
    extracted_appointments, failed_extractions = extractor.parse_all(emails)

    sheets.add_appointments(
        [(item.mail, item.appointment) for item in extracted_appointments]
    )

    for item in extracted_appointments:
        email_client.reply_success(item.mail, item.appointment)

    for item in failed_extractions:
        logger.log_error(f"{item.mail.uid}: {item.error}")
        email_client.reply_failed(item.mail, item.error)

    failed_uids = {item.mail.uid for item in failed_extractions}
    for email in emails:
        if email.uid in failed_uids:
            email_client.mark_failed(email)
        else:
            email_client.mark_completed(email)


def run(
    config: Any | None = None,
    *,
    email_client_factory: Callable = EmailClient,
    extractor_factory: Callable = AppointmentsExtractor,
    gemini_ia_client_factory: Callable = GeminiIAClient,
    openrouter_ia_client_factory: Callable = OpenRouterIAClient,
    local_ia_client_factory: Callable = LocalIAClient,
    sheets_factory: Callable = AppointmentsSheet,
    logger_factory: Callable = Logger,
    sleep: Callable = time.sleep,
    max_cycles: int | None = None,
) -> None:
    """Build integrations and poll until interrupted.

    ``max_cycles`` and the injectable factories make the application boundary
    usable in integration tests without connecting to external services.
    """
    config = config or load_config()
    credentials = json.loads(
        config.database["credentials"].read_text(encoding="utf-8")
    )
    if config.local_ia_enabled:
        ia_clients = [
            local_ia_client_factory(
                config.local_ia_base_url,
                config.local_ia_model,
                config.local_ia_timeout_seconds,
            )
        ]
    else:
        ia_clients = []
        if config.gemini_ia_api_key:
            ia_clients.append(
                gemini_ia_client_factory(
                    config.gemini_ia_api_key,
                    config.gemini_ia_model,
                )
            )
        if config.openrouter_api_key and config.open_router_model:
            ia_clients.append(
                openrouter_ia_client_factory(
                    config.openrouter_api_key,
                    config.open_router_model,
                )
            )
    if not ia_clients:
        raise ValueError("At least one IA client must be configured")
    extractor = extractor_factory(ia_clients)
    sheets = sheets_factory(
        credentials,
        config.database["sheet_id"],
        config.database["table_name"],
        config.database["email_table_name"],
    )
    logger = logger_factory()

    with email_client_factory(
        config.imap,
        config.smtp,
        config.processed_folder,
        config.failed_folder,
        config.allowed_senders,
    ) as email_client:
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            try:
                process_batch(email_client, extractor, sheets, logger)
            except ServerError as error:
                if error.code == 503:
                    logger.log_error(
                        f"An IA provider is temporarily unavailable; emails will be retried next cycle: {error}"
                    )
                else:
                    logger.log_error(str(error))
            except Exception as error:
                logger.log_error(str(error))

            cycles += 1
            if max_cycles is None or cycles < max_cycles:
                sleep(config.interval_minutes * 60)


def main() -> None:
    run()
