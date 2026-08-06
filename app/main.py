import json
import time
from collections.abc import Callable
from typing import Any

from google.genai.errors import ServerError

from .appointments_extractor import AppointmentsExtractor
from .appointments_sheet import AppointmentsSheet
from .config import load_config, load_google_credentials
from .email_client import AppointmentsEmailClient
from .ia_clients import GeminiIAClient, LocalIAClient
from .logger import Logger
from .ia_clients import OpenRouterIAClient


def process_batch(email_client, extractor, sheets, logger) -> None:
    """Process one batch of emails."""
    emails = email_client.fetch()
    logger.log_info(f"Found {len(emails)} email(s) to process.")
    results = extractor.parse_all(emails)

    for item in results:

        if item.error:
            logger.log_error(f"{item.mail.uid}: {item.error}")
            email_client.reply_failed(item.mail, item.error)
            logger.log_error(f"Failed to extract appointment from email {item.mail.uid}: {item.error}")
            email_client.mark_failed(item.mail)
            continue

        sheets.add_appointments(
            [(item.mail, appointment) for appointment in item.appointments]
        )
        email_client.mark_completed(item.mail)

        email_client.reply_success(item.mail, item.appointments)
        logger.log_info(f"Successfully processed email {item.mail.uid} and added {len(item.appointments)} appointment(s) to sheet.")


def run(
    config: Any | None = None,
    *,
    email_client_factory: Callable = AppointmentsEmailClient,
    extractor_factory: Callable = AppointmentsExtractor,
    gemini_ia_client_factory: Callable = GeminiIAClient,
    openrouter_ia_client_factory: Callable = OpenRouterIAClient,
    local_ia_client_factory: Callable = LocalIAClient,
    sheets_factory: Callable = AppointmentsSheet,
    logger_factory: Callable = Logger,
    sleep: Callable = time.sleep,
    max_cycles: int | None = None,
    ia_provider: str | None = None,
) -> None:
    """Build integrations and poll until interrupted.

    ``max_cycles`` and the injectable factories make the application boundary
    usable in integration tests without connecting to external services.
    """
    config = config or load_config()
    credentials = load_google_credentials(config.database["credentials"])
    selected_provider = ia_provider.strip().lower() if ia_provider else None
    if selected_provider not in {None, "local", "gemini", "openrouter"}:
        raise ValueError("ia_provider must be local, gemini, or openrouter")

    use_local = selected_provider == "local" or (
        selected_provider is None and config.local_ia_enabled
    )
    if use_local:
        ia_clients = [
            local_ia_client_factory(
                config.local_ia_base_url,
                config.local_ia_model,
                config.local_ia_timeout_seconds,
            )
        ]
    else:
        ia_clients = []
        if config.gemini_ia_api_key and selected_provider in {None, "gemini"}:
            ia_clients.append(
                gemini_ia_client_factory(
                    config.gemini_ia_api_key,
                    config.gemini_ia_model,
                )
            )
        if (
            config.openrouter_api_key
            and config.open_router_model
            and selected_provider in {None, "openrouter"}
        ):
            ia_clients.append(
                openrouter_ia_client_factory(
                    config.openrouter_api_key,
                    config.open_router_model,
                )
            )
    if not ia_clients:
        raise ValueError("At least one IA client must be configured")
    process_emails_individually = selected_provider in {"local", "openrouter"} or (
        selected_provider is None
        and (config.local_ia_enabled or (
            not config.gemini_ia_api_key
            and bool(config.openrouter_api_key and config.open_router_model)
        ))
    )
    extractor = extractor_factory(
        ia_clients,
        process_emails_individually=process_emails_individually,
    )
    sheets = sheets_factory(
        credentials,
        config.database["sheet_id"],
        config.database["table_name"],
        config.database["email_table_name"],
    )
    logger = logger_factory()
    logger.log_info("Email appointments recorder started.")

    with email_client_factory(
        config.imap,
        config.smtp,
        config.processed_folder,
        config.failed_folder,
        config.allowed_senders,
        config.mail_web_base_url,
    ) as email_client:
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            try:
                logger.log_info("Checking mailbox...")
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
                logger.log_info(
                    f"Waiting {config.interval_minutes} minute(s) before the next check..."
                )
                sleep(config.interval_minutes * 60)


def main() -> None:
    run()


if __name__ == "__main__":
    main()
