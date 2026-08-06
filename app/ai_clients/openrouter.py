import json
from typing import Type, TypeVar
from urllib import error, request

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class OpenRouterError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"OpenRouter request failed ({status_code}): {message}")
        self.status_code = status_code


class OpenRouterAIClient:
    def __init__(
        self,
        api_key: str,
        model_name: str,
        *,
        endpoint: str = "https://openrouter.ai/api/v1/chat/completions",
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.endpoint = endpoint

    def generate_structured_output(self, prompt: str, response_schema: Type[T]) -> T:
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "timeout": 60.0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "strict": True,
                    "schema": response_schema.model_json_schema(),
                },
            },
        }
        http_request = request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise OpenRouterError(exc.code, response_body) from exc
        except error.URLError as exc:
            raise OpenRouterError(503, str(exc.reason)) from exc

        try:
            response_data = json.loads(response_body)
            content = response_data["choices"][0]["message"]["content"]
            return response_schema.model_validate(json.loads(content))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise OpenRouterError(502, f"Invalid structured response: {response_body}") from exc
