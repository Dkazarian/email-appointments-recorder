import argparse
import time

from .config import load_settings
from .extractors import ActionExtractor, build_extractor
from .mail_client import fetch_mails, move_mail
from .mail_replier import MailReplier
from .run_logger import RunLogger
from .sinks import ResultSink, build_sink


def main() -> None:
    args = get_args()
    settings = load_settings()
    extractor = build_extractor(settings)
    sink = build_sink(settings, args.output_txt, args.output_gsheets)
    replier = MailReplier(settings)
    logger = RunLogger()
    interval_minutes = args.interval_minutes or settings.poll_interval_minutes

    while True:
        processed_count = process_cycle(settings, extractor, sink, replier, logger, args.limit)
        if not args.watch:
            break
        if processed_count > 0:
            continue
        logger.status(f"Esperando {interval_minutes} minutos antes del proximo ciclo...")
        time.sleep(interval_minutes * 60)

def get_args():
    parser = argparse.ArgumentParser(
        description="Procesa mails y actualiza un Google Sheet usando Ollama.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="Muestra esta ayuda y sale.")
    parser.add_argument("--limit", type=int, default=10, help="Cantidad maxima de mails a procesar.")
    parser.add_argument("--output-txt", nargs="?", const="", help="Guarda las acciones extraidas en un archivo de texto.")
    parser.add_argument("--output-gsheets", action="store_true", help="Guarda las acciones extraidas en Google Sheets.")
    parser.add_argument("--watch", action="store_true", help="Mantiene la app corriendo y revisa mails periodicamente.")
    parser.add_argument("--interval-minutes", type=int, help="Minutos entre ciclos. Por defecto usa POLL_INTERVAL_MINUTES.")
    parser._optionals.title = "opciones"
    args = parser.parse_args()
    if args.output_txt is not None and args.output_gsheets:
        parser.error("Usa solo un destino de salida: --output-txt o --output-gsheets.")
    return args

def process_cycle(settings, extractor: ActionExtractor, sink: ResultSink, replier: MailReplier, logger: RunLogger, limit: int) -> int:
    mails = fetch_mails(settings, limit)
    if not mails:
        logger.status("No se encontraron mails.")
        return 0

    for mail in mails:
        try:
            action = extractor.extract(mail)
            logger.action(mail, action)
            validate_processable_action(action)

            result = sink.apply(mail, action)
            logger.status(f"{mail.uid}: {result}")
            reply_processed(replier, mail, action, logger)

            move_processed_mail(settings, logger, mail.uid)
        except Exception as exc:
            logger.error(mail, exc)
            reply_error(replier, mail, exc, logger)
            move_failed_mail(settings, logger, mail.uid)
    return len(mails)


def move_processed_mail(settings, logger: RunLogger, uid: str) -> None:
    move_mail(settings, uid, settings.processed_folder)
    logger.status(f"{uid}: movido a {settings.processed_folder}")


def move_failed_mail(settings, logger: RunLogger, uid: str) -> None:
    try:
        move_mail(settings, uid, settings.failed_folder)
        logger.status(f"{uid}: movido a {settings.failed_folder}")
    except Exception as move_exc:
        logger.error_for_uid(uid, move_exc, event="fallo_movimiento")


def reply_processed(replier: MailReplier, mail, action, logger: RunLogger) -> None:
    replier.reply_processed(mail, action)
    logger.status(f"{mail.uid}: respuesta enviada")


def reply_error(replier: MailReplier, mail, exc: Exception, logger: RunLogger) -> None:
    try:
        replier.reply_error(mail, exc)
        logger.status(f"{mail.uid}: respuesta de error enviada")
    except Exception as reply_exc:
        logger.error_for_uid(mail.uid, reply_exc, event="fallo_respuesta")


class ProcessingDecisionError(RuntimeError):
    pass


def _ignored_message(action) -> str:
    if action.reason:
        return f"La IA decidio ignorar el mail: {action.reason}"
    return "La IA decidio ignorar el mail."


def validate_processable_action(action) -> None:
    if action.action == "ignore":
        raise ProcessingDecisionError(_ignored_message(action))
    if action.action == "needs_review":
        raise ProcessingDecisionError(_needs_review_message(action))
    if action.action != "append_row":
        raise ProcessingDecisionError(f"Accion no procesable: {action.action}")

    missing = [
        field
        for field in ("concepto", "monto", "estado")
        if not str(action.row.get(field) or "").strip()
    ]
    if missing:
        raise ProcessingDecisionError(f"La IA no genero una fila valida. Faltan campos: {', '.join(missing)}")

    estado = str(action.row.get("estado") or "").strip().lower()
    if estado not in {"pendiente", "pagado"}:
        raise ProcessingDecisionError(f"La IA genero un estado invalido: {estado}")


def _needs_review_message(action) -> str:
    if action.reason:
        return f"La IA no pudo generar una fila valida: {action.reason}"
    return "La IA no pudo generar una fila valida."


if __name__ == "__main__":
    main()
