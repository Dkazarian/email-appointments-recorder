import os
import unittest

from app.ia_clients.lm_studio import LocalIAClient

from .common import assert_two_email_extraction


@unittest.skipUnless(
    os.getenv("RUN_LOCAL_IA_INTEGRATION_TESTS") == "1",
    "Set RUN_LOCAL_IA_INTEGRATION_TESTS=1 to use the local LM Studio model",
)
class LocalAppointmentsExtractorIntegrationTests(unittest.TestCase):
    def test_processes_two_emails_with_real_local_model(self):
        client = LocalIAClient(
            os.getenv("LOCAL_IA_BASE_URL", "http://localhost:1234/v1"),
            os.getenv("LOCAL_IA_MODEL", "google_gemma-3-4b-it"),
            int(os.getenv("LOCAL_IA_TIMEOUT_SECONDS", "120")),
        )
        assert_two_email_extraction(self, "Local LM Studio", client)
