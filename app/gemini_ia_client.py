import os
from typing import Any, Type, TypeVar, NamedTuple
from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar('T', bound=BaseModel)

from copy import deepcopy


def _inline_json_schema(schema: dict) -> dict:
    definitions = schema.pop("$defs", {})

    def resolve(value):
        if isinstance(value, dict):
            reference = value.get("$ref")
            if reference:
                definition_name = reference.rsplit("/", 1)[-1]
                return resolve(deepcopy(definitions[definition_name]))
            return {
                key: resolve(item)
                for key, item in value.items()
                if key not in {"title", "additionalProperties"}
            }
        if isinstance(value, list):
            return [resolve(item) for item in value]
        return value

    return resolve(schema)


class GeminiIAClient:
    def __init__(self, api_key: str, model_name: str = "gemini-3.5-flash"):
        self.client = genai.Client(
            api_key=api_key,
            http_options={"timeout": 60000},
        )
        self.model_name = model_name

    def generate_structured_output(self, prompt: str, response_schema: Type[T]) -> T:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_inline_json_schema(response_schema.model_json_schema()),
                temperature=0.1,
            ),
        )
        return response.parsed
