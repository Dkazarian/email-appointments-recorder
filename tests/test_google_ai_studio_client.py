import unittest
from unittest.mock import Mock, patch

from pydantic import BaseModel

from app.ai_clients.google_ai_studio import GoogleAIStudioClient


class HelloWorld(BaseModel):
    message: str


class GoogleAIStudioClientTests(unittest.TestCase):
    @patch("app.ai_clients.google_ai_studio.genai.Client")
    def test_converts_a_dict_response_to_the_requested_pydantic_model(self, client_class):
        client_class.return_value.models.generate_content.return_value = Mock(
            parsed={"message": "Hello, world!"}
        )

        result = GoogleAIStudioClient("test-key", "test-model").generate_structured_output(
            "Say hello.", HelloWorld
        )

        self.assertIsInstance(result, HelloWorld)
        self.assertEqual(result.message, "Hello, world!")


if __name__ == "__main__":
    unittest.main()
