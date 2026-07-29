import os
import unittest

from app.appointments_extractor import AppointmentsExtractor
from app.config import load_dotenv_file
from app.email_client import EmailItem
from app.gemini_ia_client import GeminiIAClient
from app.openrouter_ia_client import OpenRouterIAClient


load_dotenv_file()

EMAILS = [
    EmailItem(
        uid="email-1",
        url=None,
        sender="secretaria@example.com",
        reply_to="secretaria@example.com",
        recipients=[],
        subject="Turno de Ana",
        sent_at=None,
        body=(
            "Ana Perez\n"
            "Laboratorio Clinica Central 24/03 15:30\n"
            "Radiografia mano izquierda Centro Norte 25/03 09:00"
        ),
    ),
    EmailItem(
        uid="email-2",
        url=None,
        sender="secretaria@example.com",
        reply_to="secretaria@example.com",
        recipients=[],
        subject="Turno de Juan",
        sent_at=None,
        body=(
            "Juan Gomez\n"
            "Radiografia mano izquierda Centro 2 14/05 19:30\n"
            "Audiometria Calle 123 15/05 10:30"
        ),
    ),
]


def assert_two_email_extraction(test_case, provider_name, ia_client):
    extractor = AppointmentsExtractor([ia_client])
    extracted, failed = extractor.parse_all(EMAILS)

    print(
        f"\n{provider_name} extractor response:\n"
        + "\n".join(
            f"{item.mail.uid}: {item.appointment.model_dump()}"
            for item in extracted
        )
    )

    test_case.assertEqual(failed, [])
    test_case.assertEqual(len(extracted), 4)
    appointments_by_email = {email.uid: [] for email in EMAILS}
    for item in extracted:
        appointments_by_email[item.mail.uid].append(item.appointment)

    test_case.assertEqual(len(appointments_by_email["email-1"]), 2)
    test_case.assertTrue(
        all(
            appointment.patient_name == "Ana Perez"
            for appointment in appointments_by_email["email-1"]
        )
    )
    test_case.assertEqual(len(appointments_by_email["email-2"]), 2)
    test_case.assertTrue(
        all(
            appointment.patient_name == "Juan Gomez"
            for appointment in appointments_by_email["email-2"]
        )
    )
    studies = {appointment.study for appointment in appointments_by_email["email-2"]}
    test_case.assertEqual(studies, {"Radiografia mano izquierda", "Audiometria"})


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

        assert_two_email_extraction(
            self,
            "OpenRouter",
            OpenRouterIAClient(api_key, model_name),
        )


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

        assert_two_email_extraction(
            self,
            "Gemini",
            GeminiIAClient(api_key, model_name),
        )


if __name__ == "__main__":
    unittest.main()
