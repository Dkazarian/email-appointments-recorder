import os
from typing import Any, Type, TypeVar, NamedTuple
from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar('T', bound=BaseModel)

class GeminiIAClient:
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def generate_structured_output(self, prompt: str, response_schema: Type[T]) -> T:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.1,
            ),
        )
        return response.parsed
