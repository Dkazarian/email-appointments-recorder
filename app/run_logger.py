import json

from .mail_client import MailItem
from .model import SheetAction


class RunLogger:
    def action(self, mail: MailItem, action: SheetAction) -> None:
        self._json(
            {
                "mail_id": mail.uid,
                "sender": mail.sender,
                "subject": mail.subject,
                "action": action.to_dict(),
            }
        )

    def error(self, mail: MailItem, exc: Exception, event: str = "fallo_procesamiento") -> None:
        self._json(
            {
                "mail_id": mail.uid,
                "sender": mail.sender,
                "subject": mail.subject,
                "event": event,
                "error": str(exc),
            }
        )

    def error_for_uid(self, uid: str, exc: Exception, event: str) -> None:
        self._json(
            {
                "mail_id": uid,
                "event": event,
                "error": str(exc),
            }
        )

    def status(self, message: str) -> None:
        print(message)

    def _json(self, record: dict) -> None:
        print(json.dumps(record, ensure_ascii=False, indent=2))
