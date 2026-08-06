import json
import unittest
from unittest.mock import Mock, patch

from pydantic import BaseModel

from app.ai_clients.lm_studio import LocalAIClient


class HelloWorld(BaseModel):
    message: str


class LocalAIClientTests(unittest.TestCase):
    @patch("app.ai_clients.lm_studio.request.urlopen")
    def test_generates_structured_output_through_lm_studio(self, urlopen):
        response = Mock()
        response.read.return_value = json.dumps(
            {
                "choices": [
                    {"message": {"content": '{"message": "Hello, world!"}'}}
                ]
            }
        ).encode("utf-8")
        urlopen.return_value.__enter__.return_value = response

        result = LocalAIClient(
            "http://localhost:1234/v1/",
            "google_gemma-3-4b-it",
            timeout_seconds=45,
        ).generate_structured_output("Say hello.", HelloWorld)

        self.assertEqual(result.message, "Hello, world!")
        sent_request = urlopen.call_args.args[0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "google_gemma-3-4b-it")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["messages"][0]["content"], "Say hello.")
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 45)


if __name__ == "__main__":
    unittest.main()
