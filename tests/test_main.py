import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from google.genai.errors import ServerError

from app.appointments_extractor import FailedItem, SuccessItem
from app.email_client import EmailItem
from app.main import process_batch
from app.models import Appointment


class MainIntegrationTests(unittest.TestCase):
    def test_process_batch_coordinates_all_integrations(self):
        successful_mail = EmailItem(
            uid="1",
            url=None,
            sender="one@example.com",
            reply_to="one@example.com",
            recipients=[],
            subject="Turno",
            sent_at=None,
            body="turno",
        )
        failed_mail = EmailItem(
            uid="2",
            url=None,
            sender="two@example.com",
            reply_to="two@example.com",
            recipients=[],
            subject="Sin turno",
            sent_at=None,
            body="sin turno",
        )
        appointment = Appointment(patient_name="Ana", study="Laboratorio")
        extractor = Mock()
        extractor.parse_all.return_value = (
            [SuccessItem(appointment, successful_mail)],
            [FailedItem("No contiene fecha", failed_mail)],
        )
        email_client = Mock()
        email_client.fetch.return_value = [successful_mail, failed_mail]
        sheets = Mock()
        logger = Mock()

        process_batch(email_client, extractor, sheets, logger)

        extractor.parse_all.assert_called_once_with([successful_mail, failed_mail])
        sheets.add_appointments.assert_called_once_with([(successful_mail, appointment)])
        email_client.reply_success.assert_called_once_with(successful_mail, appointment)
        email_client.reply_failed.assert_called_once_with(failed_mail, "No contiene fecha")
        email_client.mark_completed.assert_called_once_with(successful_mail)
        email_client.mark_failed.assert_called_once_with(failed_mail)
        logger.log_error.assert_called_once_with("2: No contiene fecha")

    def test_transient_gemini_error_leaves_emails_for_next_cycle(self):
        emails = [
            EmailItem(
                uid="1",
                url=None,
                sender="one@example.com",
                reply_to="one@example.com",
                recipients=[],
                subject="Turno",
                sent_at=None,
                body="turno",
            )
        ]
        extractor = Mock()
        extractor.parse_all.side_effect = ServerError(
            503,
            SimpleNamespace(
                body_segments=[
                    {
                        "error": {
                            "message": "Temporary outage",
                            "status": "UNAVAILABLE",
                        }
                    }
                ]
            ),
        )
        email_client = Mock()
        email_client.fetch.return_value = emails

        with self.assertRaises(ServerError):
            process_batch(email_client, extractor, Mock(), Mock())

        email_client.mark_failed.assert_not_called()
        email_client.mark_completed.assert_not_called()
        email_client.reply_failed.assert_not_called()
        email_client.reply_success.assert_not_called()


if __name__ == "__main__":
    unittest.main()
