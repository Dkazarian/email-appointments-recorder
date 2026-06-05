from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Literal
from urllib import request
from urllib.error import HTTPError, URLError

from .config import Settings
from .mail_client import MailItem


ActionType = Literal["append_row", "ignore", "needs_review"]
VALID_ACTIONS = {"append_row", "ignore", "needs_review"}


@dataclass(frozen=True)
class SheetAction:
    action: ActionType
    reason: str = ""
    row: dict[str, str | int | float | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "row": self.row,
        }


class OllamaExtractor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.system_prompt = load_prompt(settings.prompt_file)

    def extract(self, mail: MailItem) -> SheetAction:
        payload = {
            "model": self.settings.ollama_model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": _mail_prompt(mail)},
            ],
        }
        content = _post_json(
            f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
            payload,
            timeout_seconds=self.settings.ollama_timeout_seconds,
        )["message"]["content"]
        return parse_action(content)


def parse_action(content: str) -> SheetAction:
    try:
        data: Any = json.loads(content)
        return _validate_action(data)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        return SheetAction(
            action="needs_review",
            reason=f"El modelo devolvio JSON/accion invalida: {exc}. Respuesta: {content[:500]}",
            row={},
        )


def _validate_action(data: Any) -> SheetAction:
    if not isinstance(data, dict):
        raise ValueError("se esperaba un objeto JSON")

    action = data.get("action")
    if action not in VALID_ACTIONS:
        raise ValueError(f"accion no soportada: {action}")

    reason = data.get("reason") or ""
    if not isinstance(reason, str):
        reason = str(reason)

    row = data.get("row") or {}
    if not isinstance(row, dict):
        raise ValueError("row debe ser un objeto")

    normalized_row = {
        str(key): value
        for key, value in row.items()
        if value is None or isinstance(value, (str, int, float))
    }

    return SheetAction(
        action=action,
        reason=reason,
        row=normalized_row,
    )


def _mail_prompt(mail: MailItem) -> str:
    return f"""
mail_id: {mail.uid}
remitente: {mail.sender}
asunto: {mail.subject}

cuerpo:
{mail.body[:12000]}
""".strip()


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Error HTTP de Ollama {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"No se pudo conectar con Ollama en {url}: {exc}") from exc


def load_prompt(path: str) -> str:
    prompt_path = Path(path)
    if not prompt_path.exists():
        raise RuntimeError(f"No se encontro el archivo de prompt: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip()
