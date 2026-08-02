import json
from typing import Type, TypeVar
from urllib import error, request

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class OllamaError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"Ollama request failed ({status_code}): {message}")
        self.status_code = status_code


class LocalIAClient:
    """Structured-output client for a local model served by Ollama."""

    def __init__(
        self,
        base_url: str,
        model_name: str,
        timeout_seconds: int = 300,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def generate_structured_output(self, prompt: str, response_schema: Type[T]) -> T:
        payload = {
            "model": self.model_name,
            "stream": False,
            "format": response_schema.model_json_schema(),
            "messages": [{"role": "user", "content": prompt}],
        }
        http_request = request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise OllamaError(exc.code, response_body) from exc
        except error.URLError as exc:
            raise OllamaError(503, str(exc.reason)) from exc

        try:
            response_data = json.loads(response_body)
            content = response_data["message"]["content"]
            return response_schema.model_validate(json.loads(content))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise OllamaError(502, f"Invalid structured response: {response_body}") from exc
