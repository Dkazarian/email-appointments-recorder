import os
import unittest

from app.config import load_dotenv_file
from app.ai_clients import GoogleAIStudioClient

from .common import assert_fixture_extraction

load_dotenv_file()


@unittest.skipUnless(
    os.getenv("RUN_GOOGLE_AI_STUDIO_INTEGRATION_TESTS") == "1",
    "Set RUN_GOOGLE_AI_STUDIO_INTEGRATION_TESTS=1 to use the real Google AI Studio API",
)
class GoogleAIStudioAppointmentsExtractorIntegrationTests(unittest.TestCase):
    def test_processes_two_emails_with_real_google_ai_studio(self):
        api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        model_name = os.getenv("GOOGLE_AI_STUDIO_MODEL")
        self.assertTrue(api_key, "GOOGLE_AI_STUDIO_API_KEY must be configured")
        self.assertTrue(model_name, "GOOGLE_AI_STUDIO_MODEL must be configured")
        assert_fixture_extraction(
            self,
            "Google AI Studio",
            GoogleAIStudioClient(api_key, model_name),
        )
