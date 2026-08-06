import os
import unittest

from app.config import load_dotenv_file
from app.ia_clients import OpenRouterIAClient

from .common import assert_fixture_extraction

load_dotenv_file()


@unittest.skipUnless(
    os.getenv("RUN_OPENROUTER_INTEGRATION_TESTS") == "1",
    "Set RUN_OPENROUTER_INTEGRATION_TESTS=1 to use the real OpenRouter API",
)
class OpenRouterAppointmentsExtractorIntegrationTests(unittest.TestCase):
    def test_processes_two_emails_with_real_openrouter(self):
        api_key = os.getenv("OPENROUTER_API_KEY")
        model_name = os.getenv("OPEN_ROUTER_MODEL")
        self.assertTrue(api_key, "OPENROUTER_API_KEY must be configured")
        self.assertTrue(model_name, "OPEN_ROUTER_MODEL must be configured")
        assert_fixture_extraction(
            self,
            "OpenRouter",
            OpenRouterIAClient(api_key, model_name),
            process_emails_individually=True,
        )
