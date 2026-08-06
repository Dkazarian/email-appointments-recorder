import json
import unittest

from app.appointments_extractor import AppointmentsExtractor
from tests.fixtures.appointment_emails import APPOINTMENT_FIXTURES


def assert_fixture_extraction(
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
    emails = [fixture.email for fixture in APPOINTMENT_FIXTURES]
    extracted, failed = extractor.parse_all(emails)

    print(
        f"\n{provider_name} extractor response:\n"
        + "\n".join(
            f"{item.mail.uid}: {item.appointment.model_dump()}"
            for item in extracted
        )
    )

    test_case.assertEqual(failed, [])
    expected_total = sum(len(fixture.extracted) for fixture in APPOINTMENT_FIXTURES)
    test_case.assertEqual(len(extracted), expected_total)
    appointments_by_email = {email.uid: [] for email in emails}
    for item in extracted:
        appointments_by_email[item.mail.uid].append(item.appointment)

    for fixture in APPOINTMENT_FIXTURES:
        actual = appointments_by_email[fixture.email.uid]
        test_case.assertEqual(len(actual), len(fixture.extracted))
        actual_pairs = sorted((a.patient_name, a.study) for a in actual)
        expected_pairs = sorted(
            (expected.patient_name, expected.study)
            for expected in fixture.extracted
        )
        test_case.assertEqual(actual_pairs, expected_pairs)
