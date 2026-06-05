from typing import Protocol

from .config import Settings
from .mail_client import MailItem
from .model import SheetAction
from .text_sink import TextSink


class ResultSink(Protocol):
    def apply(self, mail: MailItem, action: SheetAction) -> str:
        """Persiste una accion extraida en algun destino."""


class NoopSink:
    def apply(self, mail: MailItem, action: SheetAction) -> str:
        return "no persistido"


def build_sink(settings: Settings, output_txt: str | None, dry_run: bool) -> ResultSink:
    if dry_run:
        return NoopSink()
    if output_txt is not None:
        txt_path = output_txt or settings.txt_output_path
        return TextSink(txt_path)
    return build_sheets_sink(settings)


def build_sheets_sink(settings: Settings) -> ResultSink:
    from .sheets import SheetsSink

    return SheetsSink(settings)
