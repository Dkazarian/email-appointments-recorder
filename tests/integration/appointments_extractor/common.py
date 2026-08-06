import json
import re
import unittest

from app.appointments_extractor import AppointmentsExtractor
from tests.fixtures.appointment_emails import APPOINTMENT_FIXTURES


def assert_fixture_extraction(
    test_case: unittest.TestCase,
    provider_name,
    ai_client,
):
    class PrintingAIClient:
        def generate_structured_output(self, prompt, response_schema):
            response = ai_client.generate_structured_output(
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

    extractor = AppointmentsExtractor([PrintingAIClient()])
    emails = [fixture.email for fixture in APPOINTMENT_FIXTURES]
    results = extractor.parse_all(emails)

    print(
        f"\n{provider_name} extractor response:\n"
        + "\n".join(
            f"{item.mail.uid}: {appointment.model_dump()}"
            for item in results
            for appointment in item.appointments
        )
    )

    test_case.assertTrue(all(result.error is None for result in results))
    expected_total = sum(len(fixture.extracted) for fixture in APPOINTMENT_FIXTURES)
    test_case.assertEqual(
        sum(len(result.appointments) for result in results), expected_total
    )
    appointments_by_email = {email.uid: [] for email in emails}
    for item in results:
        appointments_by_email[item.mail.uid].extend(item.appointments)

    for fixture in APPOINTMENT_FIXTURES:
        actual = appointments_by_email[fixture.email.uid]
        def matches(expected):
            if expected.study.casefold() not in current.study.casefold():
                return False
            if current.patient_name is None:
                return True
            if expected.patient_name is None:
                return True
            actual_name_parts = set(
                re.findall(r"[\wÀ-ÿ]+", current.patient_name.lower())
            )
            expected_name_parts = set(
                re.findall(r"[\wÀ-ÿ]+", expected.patient_name.lower())
            )
            return actual_name_parts == expected_name_parts

        test_case.assertEqual(len(actual), len(fixture.extracted))
        unmatched = list(fixture.extracted)
        for current in actual:
            match_index = next(
                (index for index, expected in enumerate(unmatched) if matches(expected)),
                None,
            )
            test_case.assertIsNotNone(
                match_index,
                f"Unexpected appointment extracted: {current}",
            )
            unmatched.pop(match_index)
