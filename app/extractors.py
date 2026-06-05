from typing import Protocol

from .config import Settings
from .mail_client import MailItem
from .model import OllamaExtractor, SheetAction


class ActionExtractor(Protocol):
    def extract(self, mail: MailItem) -> SheetAction:
        """Extrae una accion estructurada desde un mail."""


def build_extractor(settings: Settings) -> ActionExtractor:
    provider = settings.ai_provider.lower()
    if provider == "ollama":
        return OllamaExtractor(settings)
    raise RuntimeError(f"AI_PROVIDER no soportado: {settings.ai_provider}")
