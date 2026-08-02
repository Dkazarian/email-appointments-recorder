import json
import unittest

from app.appointments_extractor import AppointmentsExtractor
from app.email_client import EmailItem


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
            "Paciente: Ana Perez\n"
            "Turno 1 - Estudio: Laboratorio; Clínica: Clinica Central; "
            "Fecha: 24/03; Hora: 15:30\n"
            "Turno 2 - Estudio: Radiografia; Detalle: Radiografia mano izquierda; "
            "Clínica: Centro Norte; Fecha: 25/03; Hora: 09:00"
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
            "Paciente: Juan Gomez\n"
            "Turno 1 - Estudio: Radiografia; Detalle: Radiografia mano izquierda; "
            "Clínica: Centro Dos; Fecha: 14/05; Hora: 19:30\n"
            "Turno 2 - Estudio: Audiometria; Clínica: Calle 123; "
            "Fecha: 15/05; Hora: 10:30"
        ),
    ),
]


def assert_two_email_extraction(
    test_case: unittest.TestCase,
    provider_name,
    ia_client,
    *,
    process_emails_individually: bool = False,
):
    class PrintingIAClient:
        def generate_structured_output(self, prompt, response_schema):
            response = ia_client.generate_structured_output(
                prompt=prompt,
                response_schema=response_schema,
            )
            printable_response = (
                response.model_dump() if hasattr(response, "model_dump") else response
            )
            print(
                f"\n{provider_name} response:\n"
                + json.dumps(
                    printable_response,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return response

    extractor = AppointmentsExtractor(
        [PrintingIAClient()],
        process_emails_individually=process_emails_individually,
    )
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
    test_case.assertEqual(studies, {"Radiografia", "Audiometria"})
