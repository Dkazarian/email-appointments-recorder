import unittest
from unittest.mock import Mock

from app.appointments_extractor import (
    AppointmentExtracted,
    AppointmentsExtractor,
    FailedItem,
    IAExtractionResponse,
    SuccessItem,
)
from app.email_client import EmailItem


class AppointmentsExtractorTests(unittest.TestCase):
    def setUp(self):
        self.mail = EmailItem(
            uid="42",
            url=None,
            sender="secretaria@gmail.com",
            reply_to="secretaria@gmail.com",
            recipients=["planilla@example.com"],
            subject="Turno",
            sent_at=None,
            body="Radiografia el 24/3 a las 15:55 para Ernesto",
        )

    def test_parse_all_maps_gemini_results_back_to_emails(self):
        ia_client = Mock()
        ia_client.generate_structured_output.return_value = IAExtractionResponse(
            extracted_appointments=[
                AppointmentExtracted(
                    email_id="42",
                    patient_name="Ernesto",
                    study="Radiografia",
                    date="24/3",
                    time="15:55",
                )
            ]
        )
        extractor = AppointmentsExtractor(ia_client)

        extracted, failed = extractor.parse_all([self.mail])

        self.assertEqual(len(extracted), 1)
        self.assertIsInstance(extracted[0], SuccessItem)
        self.assertIs(extracted[0].mail, self.mail)
        self.assertEqual(extracted[0].appointment.patient_name, "Ernesto")
        self.assertEqual(failed, [])
        ia_client.generate_structured_output.assert_called_once()

    def test_parse_all_maps_failures_back_to_emails(self):
        ia_client = Mock()
        ia_client.generate_structured_output.return_value = IAExtractionResponse(
            failed_emails=[{"email_id": "42", "error_message": "Sin turno"}]
        )
        extractor = AppointmentsExtractor(ia_client)

        extracted, failed = extractor.parse_all([self.mail])

        self.assertEqual(extracted, [])
        self.assertEqual(len(failed), 1)
        self.assertIsInstance(failed[0], FailedItem)
        self.assertEqual(failed[0].error, "Sin turno")
        self.assertIs(failed[0].mail, self.mail)


if __name__ == "__main__":
    unittest.main()
