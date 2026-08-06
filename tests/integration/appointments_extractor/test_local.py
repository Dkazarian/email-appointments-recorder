import os
import unittest

from app.ai_clients.lm_studio import LocalAIClient

from .common import assert_fixture_extraction


@unittest.skipUnless(
    os.getenv("RUN_LOCAL_AI_INTEGRATION_TESTS") == "1",
    "Set RUN_LOCAL_AI_INTEGRATION_TESTS=1 to use the local LM Studio model",
)
class LocalAppointmentsExtractorIntegrationTests(unittest.TestCase):
    def test_processes_two_emails_with_real_local_model(self):
        client = LocalAIClient(
            os.getenv("LOCAL_AI_BASE_URL", "http://localhost:1234/v1"),
            os.getenv("LOCAL_AI_MODEL", "google_gemma-3-4b-it"),
            int(os.getenv("LOCAL_AI_TIMEOUT_SECONDS", "120")),
        )
        assert_fixture_extraction(
            self,
            "Local LM Studio",
            client,
        )
