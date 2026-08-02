import unittest
from unittest.mock import Mock, patch

from pydantic import BaseModel

from app.ia_clients.gemini import GeminiIAClient


class HelloWorld(BaseModel):
    message: str


class GeminiIAClientTests(unittest.TestCase):
    @patch("app.ia_clients.gemini.genai.Client")
    def test_converts_a_dict_response_to_the_requested_pydantic_model(self, client_class):
        client_class.return_value.models.generate_content.return_value = Mock(
            parsed={"message": "Hello, world!"}
        )

        result = GeminiIAClient("test-key", "test-model").generate_structured_output(
            "Say hello.", HelloWorld
        )

        self.assertIsInstance(result, HelloWorld)
        self.assertEqual(result.message, "Hello, world!")


if __name__ == "__main__":
    unittest.main()
