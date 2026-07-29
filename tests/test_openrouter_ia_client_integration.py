import os
import unittest

from pydantic import BaseModel

from app.config import load_dotenv_file
from app.openrouter_ia_client import OpenRouterIAClient


load_dotenv_file()


@unittest.skipUnless(
    os.getenv("RUN_OPENROUTER_INTEGRATION_TESTS") == "1",
    "Set RUN_OPENROUTER_INTEGRATION_TESTS=1 to use the real OpenRouter API",
)
class OpenRouterIAClientIntegrationTests(unittest.TestCase):
    def test_generate_structured_output_with_hello_world_schema(self):
        api_key = os.getenv("OPENROUTER_API_KEY")
        model_name = os.getenv("OPEN_ROUTER_MODEL")
        self.assertTrue(api_key, "OPENROUTER_API_KEY must be configured")
        self.assertTrue(model_name, "OPEN_ROUTER_MODEL must be configured")

        class HelloWorld(BaseModel):
            message: str

        client = OpenRouterIAClient(api_key, model_name)

        result = client.generate_structured_output(
            "Return a HelloWorld object with the message exactly 'Hello, world!'.",
            HelloWorld,
        )

        self.assertIsInstance(result, HelloWorld)
        self.assertEqual(result.message, "Hello, world!")


if __name__ == "__main__":
    unittest.main()
