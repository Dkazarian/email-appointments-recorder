import os
import unittest

from app.config import load_dotenv_file
from app.ia_clients import GeminiIAClient

from .common import assert_fixture_extraction

load_dotenv_file()


@unittest.skipUnless(
    os.getenv("RUN_GEMINI_INTEGRATION_TESTS") == "1",
    "Set RUN_GEMINI_INTEGRATION_TESTS=1 to use the real Gemini API",
)
class GeminiAppointmentsExtractorIntegrationTests(unittest.TestCase):
    def test_processes_two_emails_with_real_gemini(self):
        api_key = os.getenv("GEMINI_IA_API_KEY")
        model_name = os.getenv("GEMINI_IA_MODEL")
        self.assertTrue(api_key, "GEMINI_IA_API_KEY must be configured")
        self.assertTrue(model_name, "GEMINI_IA_MODEL must be configured")
        assert_fixture_extraction(
            self,
            "Gemini",
            GeminiIAClient(api_key, model_name),
        )
