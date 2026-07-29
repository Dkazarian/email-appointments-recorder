from dataclasses import dataclass
from email import policy
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr
from html.parser import HTMLParser
import imaplib
import re



@dataclass(frozen=True)
class EmailItem:
    uid: str
    subject: str
    sender: str
    reply_to: str
    message_id: str
    references: str
    body: str


class EmailClient:
    def __init__(self, imap: object, smtp: object, processed_folder: str, failed_folder: str):
        self._imap_host = imap["host"]
        self._imap_port = imap["port"]
        self._imap_user = imap["username"]
        self.smtp_user = smtp["username"]
        self._imap_password = imap["password"]
        self._imap_folder = imap["folder"]
        self._imap_search = imap["search"]
        self._processed_folder = processed_folder
        self._failed_folder = failed_folder
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
            mails.append(
                EmailItem(
                    uid=uid,
                    subject=_decode_mime_header(msg.get("Subject", "")),
                    sender=parseaddr(msg.get("From", ""))[1],
                    reply_to=parseaddr(msg.get("Reply-To") or msg.get("From", ""))[1],
                    message_id=msg.get("Message-ID", ""),
                    references=msg.get("References", ""),
                    body=_extract_body(msg),
                )
            )
        return mails

    def mark_seen(self, uid: str) -> None:
        self._require_imap().uid("store", uid, "+FLAGS", r"(\Seen)")

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


def _extract_body(msg: Message) -> str:
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is None:
        return ""

    text = body.get_content()
    if body.get_content_type() == "text/html":
        text = _html_to_text(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


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

    @property
    def text(self) -> str:
        return re.sub(r"\s+\n", "\n", "\n".join(self._parts)).strip()

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._parts.append(text)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"br", "p", "div", "tr", "li"}:
            self._parts.append("\n")
