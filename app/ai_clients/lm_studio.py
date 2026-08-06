import json
from typing import Type, TypeVar
from urllib import error, request

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LocalAIError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"Local AI request failed ({status_code}): {message}")
        self.status_code = status_code


class LocalAIClient:
    """Structured-output client for a local model served by LM Studio."""

    def __init__(self, base_url: str, model_name: str, timeout_seconds: int = 300):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def generate_structured_output(self, prompt: str, response_schema: Type[T]) -> T:
        payload = {
            "model": self.model_name,
            "stream": False,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__.lower(),
                    "schema": response_schema.model_json_schema(),
                    "strict": True,
                },
            },
        }
        http_request = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise LocalAIError(exc.code, response_body) from exc
        except error.URLError as exc:
            raise LocalAIError(503, str(exc.reason)) from exc

        try:
            response_data = json.loads(response_body)
            content = response_data["choices"][0]["message"]["content"]
            return response_schema.model_validate(json.loads(content))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LocalAIError(502, f"Invalid structured response: {response_body}") from exc
