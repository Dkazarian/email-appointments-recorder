from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.utils import (
    format_datetime,
    getaddresses,
    make_msgid,
    parsedate_to_datetime,
    parseaddr,
)
from html.parser import HTMLParser
import imaplib
import re
import smtplib
from collections.abc import Collection
from urllib.parse import quote

from .models import Appointment


@dataclass(frozen=True)
class EmailItem:
    uid: str
    url: str | None
    sender: str
    reply_to: str
    recipients: list[str]
    subject: str
    sent_at: datetime | None
    body: str


class EmailClient:
    def __init__(
        self,
        imap: object,
        smtp: object,
        processed_folder: str,
        failed_folder: str,
        allowed_senders: Collection[str] | None = None,
    ):
        self._imap_host = imap["host"]
        self._imap_port = imap["port"]
        self._imap_user = imap["username"]
        self._smtp_host = smtp["host"]
        self._smtp_port = smtp["port"]
        self.smtp_user = smtp["username"]
        self._smtp_password = smtp["password"]
        self._imap_password = imap["password"]
        self._imap_folder = imap["folder"]
        self._imap_search = imap["search"]
        self._processed_folder = processed_folder
        self._failed_folder = failed_folder
        self._allowed_senders = {
            sender.strip().lower() for sender in (allowed_senders or ()) if sender.strip()
        }
        self._imap: imaplib.IMAP4_SSL | None = None

    def __enter__(self) -> "EmailClient":
        self._connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._disconnect()

    def _connect(self) -> None:
        self._imap = imaplib.IMAP4_SSL(self._imap_host, self._imap_port)
        self._imap.login(self._imap_user, self._imap_password)
        self._imap.select(self._imap_folder)

    def _disconnect(self) -> None:
        if not self._imap:
            return
        try:
            self._imap.close()
        except imaplib.IMAP4.error:
            pass
        try:
            self._imap.logout()
        except imaplib.IMAP4.error:
            pass
        self._imap = None

    def reconnect(self) -> None:
        self._disconnect()
        self._connect()

    def fetch(self, limit: int = 10) -> list[EmailItem]:
        imap = self._require_imap()
        status, data = imap.uid("search", None, self._imap_search)
        if status != "OK":
            raise RuntimeError(f"Fallo la busqueda IMAP: {status}")

        uids = data[0].split()[:limit]
        mails: list[EmailItem] = []
        for raw_uid in uids:
            uid = raw_uid.decode("utf-8")
            status, msg_data = imap.uid("fetch", raw_uid, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = message_from_bytes(raw, policy=policy.default)
            sender = parseaddr(msg.get("From", ""))[1]
            if self._allowed_senders and sender.lower() not in self._allowed_senders:
                continue
            mails.append(
                EmailItem(
                    uid=uid,
                    url=_gmail_url(msg.get("Message-ID", "")),
                    sender=sender,
                    reply_to=parseaddr(msg.get("Reply-To") or msg.get("From", ""))[1],
                    recipients=_recipients(msg),
                    subject=_decode_mime_header(msg.get("Subject", "")),
                    sent_at=_mail_datetime(msg.get("Date", "")),
                    body=_extract_body(msg),
                )
            )
        return mails

    def mark_seen(self, uid: str) -> None:
        self._require_imap().uid("store", uid, "+FLAGS", r"(\Seen)")

    def mark_completed(self, email: EmailItem | str) -> None:
        uid = email.uid if isinstance(email, EmailItem) else email
        self.mark_seen(uid)
        self.move(uid, self._processed_folder)

    def mark_failed(self, email: EmailItem | str) -> None:
        uid = email.uid if isinstance(email, EmailItem) else email
        self.mark_seen(uid)
        self.move(uid, self._failed_folder)

    def send(self, recipient: str, subject: str, body: str) -> None:
        """Send a plain-text email using the configured SMTP account."""
        message = EmailMessage()
        message["From"] = self.smtp_user
        message["To"] = recipient
        message["Subject"] = subject
        message["Date"] = format_datetime(datetime.now(timezone.utc))
        message["Message-ID"] = make_msgid()
        message.set_content(body)

        if self._smtp_port == 465:
            with smtplib.SMTP_SSL(self._smtp_host, self._smtp_port) as smtp:
                smtp.login(self.smtp_user, self._smtp_password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(self._smtp_host, self._smtp_port) as smtp:
            smtp.starttls()
            smtp.login(self.smtp_user, self._smtp_password)
            smtp.send_message(message)

    def delete(self, email: EmailItem | str) -> None:
        """Permanently delete an email from the currently selected folder."""
        uid = email.uid if isinstance(email, EmailItem) else email
        imap = self._require_imap()
        status, data = imap.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
        if status != "OK":
            raise RuntimeError(f"No se pudo eliminar el mail {uid}: {data}")
        imap.expunge()

    def reply_success(self, email: EmailItem, appointment: Appointment) -> None:
        self._send_reply(
            email,
            "El turno fue agregado correctamente a la planilla.\n\n"
            f"Paciente: {appointment.patient_name or 'No identificado'}\n"
            f"Estudio: {appointment.study or 'No identificado'}\n"
            f"Detalle: {appointment.study_detail or 'No especificado'}\n"
            f"Clínica: {appointment.clinic or 'No identificada'}\n"
            f"Fecha y hora: {' '.join(value for value in (appointment.date, appointment.time) if value) or 'No identificada'}\n",
        )

    def reply_failed(self, email: EmailItem, error: str) -> None:
        self._send_reply(
            email,
            "No se pudo registrar el turno en la planilla.\n\n"
            f"Motivo: {error}\n",
        )

    def _send_reply(self, email: EmailItem, body: str) -> None:
        self.send(
            email.reply_to or email.sender,
            _reply_subject(email.subject),
            f"Hola,\n\n{body}\nSaludos.\n",
        )

    def move(self, uid: str, folder: str) -> None:
        try:
            self._move_once(uid, folder)
        except (imaplib.IMAP4.abort, RuntimeError) as exc:
            if not _is_retriable_imap_error(exc):
                raise
            self.reconnect()
            self._move_once(uid, folder)

    def _move_once(self, uid: str, folder: str) -> None:
        imap = self._require_imap()
        self.ensure_folder(folder)

        status, _ = imap.uid("MOVE", uid, folder)
        if status == "OK":
            return

        status, data = imap.uid("COPY", uid, folder)
        if status != "OK":
            raise RuntimeError(f"No se pudo copiar el mail {uid} a {folder}: {data}")

        status, data = imap.uid("STORE", uid, "+FLAGS", r"(\Deleted)")
        if status != "OK":
            raise RuntimeError(f"No se pudo marcar el mail {uid} como eliminado despues de copiarlo: {data}")
        imap.expunge()

    def ensure_folder(self, folder: str) -> None:
        imap = self._require_imap()
        status, data = imap.create(folder)
        if status not in {"OK", "NO"}:
            raise RuntimeError(f"No se pudo crear la carpeta IMAP {folder}: {data}")

    def _require_imap(self) -> imaplib.IMAP4_SSL:
        if not self._imap:
            raise RuntimeError("El cliente IMAP no esta conectado")
        return self._imap


def fetch_mails(imap: object, smtp: object, processed_folder: str, failed_folder: str, limit: int) -> list[EmailItem]:
    with EmailClient(imap, smtp, processed_folder, failed_folder) as mail_client:
        return mail_client.fetch(limit)


def move_mail(imap: object, smtp: object, processed_folder: str, failed_folder: str, uid: str, folder: str) -> None:
    with EmailClient(imap, smtp, processed_folder, failed_folder) as mail_client:
        mail_client.move(uid, folder)


def _decode_mime_header(value: str) -> str:
    return str(make_header(decode_header(value)))


def _reply_subject(subject: str) -> str:
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"


def _recipients(msg: Message) -> list[str]:
    headers = msg.get_all("To", []) + msg.get_all("Cc", [])
    return [address for _, address in getaddresses(headers) if address]


def _gmail_url(message_id: str) -> str | None:
    """Build a Gmail search link for a message copied by BCC."""
    message_id = message_id.strip().strip("<>")
    if not message_id:
        return None
    query = quote(f"rfc822msgid:{message_id}", safe="")
    return f"https://mail.google.com/mail/u/0/#search/{query}"


def _mail_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None


def _extract_body(msg: Message) -> str:
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is None:
        return ""

    text = body.get_content()
    if body.get_content_type() == "text/html":
        text = _html_to_text(text)
    text = _remove_quoted_conversation(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _remove_quoted_conversation(text: str) -> str:
    """Keep the newest reply and discard common quoted-reply sections."""
    reply_marker = re.compile(
        r"(?im)^\s*(?:"
        r"el\s+.+?\s+escribi[oó]:|"
        r"on\s+.+?\s+wrote:|"
        r"-{2,}\s*(?:original message|mensaje original|forwarded message|mensaje reenviado)\s*-{2,}|"
        r"(?:begin forwarded message|inicio del mensaje reenviado):|"
        r"(?:original message|mensaje original):|"
        r"de:\s+|"
        r"from:\s+|"
        r"^_{5,}"
        r")"
    )
    text = reply_marker.split(text, maxsplit=1)[0]
    quoted_line = re.search(r"(?m)^\s*>+", text)
    if quoted_line:
        text = text[:quoted_line.start()]
    return text.rstrip()


def _html_to_text(html: str) -> str:
    parser = _TextHTMLParser()
    parser.feed(html)
    return parser.text


def _is_retriable_imap_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "server shutting down" in text or "socket error" in text or "connection" in text or "abort" in text


class _TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._quoted_depth = 0

    @property
    def text(self) -> str:
        return re.sub(r"\s+\n", "\n", "\n".join(self._parts)).strip()

    def handle_data(self, data: str) -> None:
        if self._quoted_depth:
            return
        text = data.strip()
        if text:
            self._parts.append(text)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "blockquote":
            self._quoted_depth += 1
            return
        if self._quoted_depth:
            return
        if tag.lower() in {"br", "p", "div", "tr", "li"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "blockquote" and self._quoted_depth:
            self._quoted_depth -= 1
