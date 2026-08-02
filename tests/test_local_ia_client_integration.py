import os
import unittest

from pydantic import BaseModel

from app.ia_clients.lm_studio import LocalIAClient, LocalIAError


class HelloWorld(BaseModel):
    message: str


@unittest.skipUnless(
    os.getenv("RUN_LOCAL_IA_INTEGRATION_TESTS") == "1",
    "Set RUN_LOCAL_IA_INTEGRATION_TESTS=1 to use the local LM Studio model",
)
class LocalIAClientIntegrationTests(unittest.TestCase):
    def test_generates_structured_output_with_real_lm_studio_model(self):
        client = LocalIAClient(
            os.getenv("LOCAL_IA_BASE_URL", "http://localhost:1234/v1"),
            os.getenv("LOCAL_IA_MODEL", "google_gemma-3-4b-it"),
            timeout_seconds=int(os.getenv("LOCAL_IA_TIMEOUT_SECONDS", "120")),
        )

        try:
            result = client.generate_structured_output(
                "Reply with the exact JSON object {\"message\": \"GEMMA_OK\"}.",
                HelloWorld,
            )
        except LocalIAError as error:
            self.fail(str(error))

        self.assertEqual(result.message, "GEMMA_OK")


if __name__ == "__main__":
    unittest.main()
