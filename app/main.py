import argparse
import time

from .config import load_settings
from .extractors import ActionExtractor, build_extractor
from .mail_client import MailClient
from .run_logger import RunLogger
from .sinks import ResultSink, build_sink


def main() -> None:
    args = get_args()
    settings = load_settings()
    extractor = build_extractor(settings)
    sink = build_sink(settings, args.output_txt, args.dry_run)
    logger = RunLogger()
    interval_minutes = args.interval_minutes or settings.poll_interval_minutes

    while True:
        process_cycle(settings, extractor, sink, logger, args.limit, args.dry_run)
        if not args.watch:
            break
        logger.status(f"Esperando {interval_minutes} minutos antes del proximo ciclo...")
        time.sleep(interval_minutes * 60)

def get_args():
    parser = argparse.ArgumentParser(
        description="Procesa mails y actualiza un Google Sheet usando Ollama.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="Muestra esta ayuda y sale.")
    parser.add_argument("--limit", type=int, default=10, help="Cantidad maxima de mails a procesar.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra las acciones extraidas sin escribir ni mover mails.")
    parser.add_argument("--output-txt", nargs="?", const="", help="Guarda las acciones extraidas en un archivo de texto en vez de Google Sheets.")
    parser.add_argument("--watch", action="store_true", help="Mantiene la app corriendo y revisa mails periodicamente.")
    parser.add_argument("--interval-minutes", type=int, help="Minutos entre ciclos. Por defecto usa POLL_INTERVAL_MINUTES.")
    parser._optionals.title = "opciones"
    return parser.parse_args()

def process_cycle(settings, extractor: ActionExtractor, sink: ResultSink, logger: RunLogger, limit: int, dry_run: bool) -> None:
    with MailClient(settings) as mail_client:
        mails = mail_client.fetch(limit)
        if not mails:
            logger.status("No se encontraron mails.")
            return

        for mail in mails:
            try:
                action = extractor.extract(mail)
                logger.action(mail, action)

                result = sink.apply(mail, action)
                logger.status(f"{mail.uid}: {result}")

                if settings.mark_processed:
                    mail_client.mark_seen(mail.uid)
                move_processed_mail(mail_client, settings, logger, mail.uid, dry_run)
            except Exception as exc:
                logger.error(mail, exc)
                move_failed_mail(mail_client, settings, logger, mail.uid, dry_run)


def move_processed_mail(mail_client: MailClient, settings, logger: RunLogger, uid: str, dry_run: bool) -> None:
    if dry_run:
        return
    mail_client.move(uid, settings.processed_folder)
    logger.status(f"{uid}: movido a {settings.processed_folder}")


def move_failed_mail(mail_client: MailClient, settings, logger: RunLogger, uid: str, dry_run: bool) -> None:
    if dry_run:
        return
    try:
        mail_client.move(uid, settings.failed_folder)
        logger.status(f"{uid}: movido a {settings.failed_folder}")
    except Exception as move_exc:
        logger.error_for_uid(uid, move_exc, event="fallo_movimiento")


if __name__ == "__main__":
    main()
