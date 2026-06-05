from datetime import datetime, timezone
import json
from pathlib import Path

from .mail_client import MailItem
from .model import SheetAction


class TextSink:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def apply(self, mail: MailItem, action: SheetAction) -> str:
        record = {
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "mail_id": mail.uid,
            "sender": mail.sender,
            "subject": mail.subject,
            "action": action.to_dict(),
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False, indent=2))
            file.write("\n\n")
        return f"agregado a {self.path}"
