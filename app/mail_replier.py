import json
from email.message import EmailMessage
import smtplib

from .config import Settings
from .mail_client import MailItem
from .model import SheetAction


class MailReplier:
    def __init__(self, settings: Settings):
        self.settings = settings

    def reply_processed(self, mail: MailItem, action: SheetAction) -> None:
        body = "\n".join(
            [
                "Procesado.",
                "",
                "Datos extraidos:",
                json.dumps(action.to_dict(), ensure_ascii=False, indent=2),
            ]
        )
        self._send_reply(mail, body)

    def reply_error(self, mail: MailItem, exc: Exception) -> None:
        body = "\n".join(
            [
                "Error al procesar el mail.",
                "",
                "Error:",
                str(exc),
                "",
                "Mensaje recibido:",
                mail.body[:4000],
            ]
        )
        self._send_reply(mail, body)

    def _send_reply(self, mail: MailItem, body: str) -> None:
        if not mail.reply_to:
            raise RuntimeError("No se encontro destinatario para responder el mail")

        message = EmailMessage()
        message["From"] = _clean_header(self.settings.smtp_user)
        message["To"] = _clean_header(mail.reply_to)
        message["Subject"] = _reply_subject(mail.subject)
        if mail.message_id:
            message["In-Reply-To"] = _clean_header(mail.message_id)
            message["References"] = _reply_references(mail.references, mail.message_id)
        message.set_content(body)

        with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as smtp:
            smtp.login(self.settings.smtp_user, self.settings.smtp_password)
            smtp.send_message(message)


def _reply_subject(subject: str) -> str:
    subject = _clean_header(subject)
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


def _reply_references(references: str, message_id: str) -> str:
    parts = [_clean_header(references), _clean_header(message_id)]
    return " ".join(part for part in parts if part)


def _clean_header(value: str) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
