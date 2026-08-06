import json
import time
from collections.abc import Callable
from typing import Any

from google.genai.errors import ServerError

from .appointments_extractor import AppointmentsExtractor
from .appointments_sheet import AppointmentsSheet
from .config import load_config, load_google_credentials
from .email_client import AppointmentsEmailClient
from .ai_clients import GoogleAIStudioClient, LocalAIClient
from .logger import Logger
from .ai_clients import OpenRouterAIClient


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
    google_ai_studio_client_factory: Callable = GoogleAIStudioClient,
    openrouter_ai_client_factory: Callable = OpenRouterAIClient,
    local_ai_client_factory: Callable = LocalAIClient,
    sheets_factory: Callable = AppointmentsSheet,
    logger_factory: Callable = Logger,
    sleep: Callable = time.sleep,
    max_cycles: int | None = None,
    ai_provider: str | None = None,
) -> None:
    """Build integrations and poll until interrupted.

    ``max_cycles`` and the injectable factories make the application boundary
    usable in integration tests without connecting to external services.
    """
    config = config or load_config()
    credentials = load_google_credentials(config.database["credentials"])
    selected_provider = ai_provider.strip().lower() if ai_provider else None
    if selected_provider not in {None, "local", "google_ai_studio", "openrouter"}:
        raise ValueError("ai_provider must be local, google_ai_studio, or openrouter")

    use_local = selected_provider == "local" or (
        selected_provider is None and config.local_ai_enabled
    )
    if use_local:
        ai_clients = [
            local_ai_client_factory(
                config.local_ai_base_url,
                config.local_ai_model,
                config.local_ai_timeout_seconds,
            )
        ]
    else:
        ai_clients = []
        if config.google_ai_studio_api_key and selected_provider in {None, "google_ai_studio"}:
            ai_clients.append(
                google_ai_studio_client_factory(
                    config.google_ai_studio_api_key,
                    config.google_ai_studio_model,
                )
            )
        if (
            config.openrouter_api_key
            and config.open_router_model
            and selected_provider in {None, "openrouter"}
        ):
            ai_clients.append(
                openrouter_ai_client_factory(
                    config.openrouter_api_key,
                    config.open_router_model,
                )
            )
    if not ai_clients:
        raise ValueError("At least one AI client must be configured")
    extractor = extractor_factory(ai_clients)
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
                        f"An AI provider is temporarily unavailable; emails will be retried next cycle: {error}"
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
