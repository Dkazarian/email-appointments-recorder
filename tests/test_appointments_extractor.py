import unittest
from unittest.mock import Mock

from app.appointments_extractor import (
    AppointmentsExtractor,
    ExtractionResult,
    AIExtractionResponse,
)
from app.email_client import EmailItem
from app.models import Appointment


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

    def test_parse_returns_provider_appointments_for_email(self):
        ai_client = Mock()
        appointment = Appointment(
            patient_name="Ernesto",
            study="Radiografia",
            study_detail="Radiografia mano izquierda",
            date="24/03/2026",
            time="15:55",
        )
        ai_client.generate_structured_output.return_value = AIExtractionResponse(
            appointments=[appointment]
        )

        result = AppointmentsExtractor(ai_client).parse(self.mail)

        self.assertIsInstance(result, ExtractionResult)
        self.assertIs(result.mail, self.mail)
        self.assertEqual(result.appointments, [appointment])
        self.assertIsNone(result.error)
        ai_client.generate_structured_output.assert_called_once()

    def test_parse_all_processes_each_email_individually(self):
        ai_client = Mock()
        ai_client.generate_structured_output.return_value = AIExtractionResponse(
            appointments=[Appointment(study="Radiografia", date="24/03/2026")]
        )
        extractor = AppointmentsExtractor(ai_client)

        results = extractor.parse_all([self.mail, self.mail])

        self.assertEqual(len(results), 2)
        self.assertEqual(ai_client.generate_structured_output.call_count, 2)

    def test_parse_normalizes_literal_null_values(self):
        ai_client = Mock()
        ai_client.generate_structured_output.return_value = AIExtractionResponse(
            appointments=[
                Appointment(
                    patient_name="null",
                    clinic_or_professional=" NONE ",
                    study="TAC",
                    study_detail="null",
                    date="05/05/2026",
                    time="null",
                )
            ]
        )

        result = AppointmentsExtractor(ai_client).parse(self.mail)

        appointment = result.appointments[0]
        self.assertIsNone(appointment.patient_name)
        self.assertIsNone(appointment.clinic_or_professional)
        self.assertEqual(appointment.study, "TAC")
        self.assertIsNone(appointment.study_detail)
        self.assertEqual(appointment.date, "05/05/2026")
        self.assertIsNone(appointment.time)

    def test_parse_returns_provider_error(self):
        ai_client = Mock()
        ai_client.generate_structured_output.return_value = AIExtractionResponse(
            error_message="Sin fecha"
        )

        result = AppointmentsExtractor(ai_client).parse(self.mail)

        self.assertEqual(result.appointments, [])
        self.assertEqual(result.error, "Sin fecha")

    def test_parse_adds_error_when_provider_returns_neither_result_nor_error(self):
        ai_client = Mock()
        ai_client.generate_structured_output.return_value = AIExtractionResponse()

        result = AppointmentsExtractor(ai_client).parse(self.mail)

        self.assertEqual(result.appointments, [])
        self.assertEqual(result.error, "La AI no pudo extraer un turno de este correo")

    def test_parse_uses_next_ai_client_when_first_one_fails(self):
        unavailable_client = Mock()
        unavailable_client.generate_structured_output.side_effect = RuntimeError(
            "temporary provider failure"
        )
        fallback_client = Mock()
        fallback_client.generate_structured_output.return_value = AIExtractionResponse(
            error_message="Sin turno"
        )

        result = AppointmentsExtractor(
            [unavailable_client, fallback_client]
        ).parse(self.mail)

        self.assertEqual(result.error, "Sin turno")
        unavailable_client.generate_structured_output.assert_called_once()
        fallback_client.generate_structured_output.assert_called_once()

    def test_prompt_includes_natural_date_instructions_and_email(self):
        prompt = AppointmentsExtractor(Mock())._build_prompt(self.mail)

        self.assertIn("Asunto: Turno", prompt)
        self.assertIn("Extrae todos los turnos médicos", prompt)
        self.assertIn("fechas escritas naturalmente por personas", prompt)
        self.assertIn("3 de agosto de 2026", prompt)
        self.assertIn("Contenido:", prompt)


if __name__ == "__main__":
    unittest.main()
