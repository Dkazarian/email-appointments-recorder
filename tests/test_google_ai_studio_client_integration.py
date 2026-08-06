import os
import unittest

from pydantic import BaseModel

from app.config import load_dotenv_file
from app.ai_clients import GoogleAIStudioClient


# Load the repository's .env before checking the opt-in flag or API key.
load_dotenv_file()


@unittest.skipUnless(
    os.getenv("RUN_GOOGLE_AI_STUDIO_INTEGRATION_TESTS") == "1",
    "Set RUN_GOOGLE_AI_STUDIO_INTEGRATION_TESTS=1 to use the real Google AI Studio API",
)
class GoogleAIStudioClientIntegrationTests(unittest.TestCase):
    def test_generate_structured_output_with_hello_world_schema(self):
        api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        self.assertTrue(
            api_key,
            "GOOGLE_AI_STUDIO_API_KEY must be set in .env or the environment",
        )

        class HelloWorld(BaseModel):
            message: str

        client = GoogleAIStudioClient(
            api_key,
            os.getenv("GOOGLE_AI_STUDIO_MODEL", "gemini-2.0-flash"),
        )

        result = client.generate_structured_output(
            "Return a HelloWorld object with the message exactly 'Hello, world!'.",
            HelloWorld,
        )

        self.assertIsInstance(result, HelloWorld)
        self.assertEqual(result.message, "Hello, world!")


if __name__ == "__main__":
    unittest.main()
