import os
import time
import unittest
import uuid

from app.config import load_config
from app.email_client import EmailClient
from app.models import Appointment


@unittest.skipUnless(
    os.getenv("RUN_EMAIL_INTEGRATION_TESTS") == "1",
    "Set RUN_EMAIL_INTEGRATION_TESTS=1 to use the real mailbox",
)
class EmailIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()

    def test_fetch(self):
        subject = self._subject("fetch")
        self.addCleanup(self._clean_emails, subject)

        email = self._seed_email(subject)

        self.assertEqual(email.subject, subject)
        self.assertEqual(email.body, "Correo de prueba de integracion.")

    def test_mark_completed(self):
        subject = self._subject("mark-completed")
        self.addCleanup(self._clean_emails, subject)
        email = self._seed_email(subject)

        with self._client() as client:
            client.mark_completed(email)

        self.assertIsNotNone(self._wait_for_email(subject, self.config.processed_folder))

    def test_mark_failed(self):
        subject = self._subject("mark-failed")
        self.addCleanup(self._clean_emails, subject)
        email = self._seed_email(subject)

        with self._client() as client:
            client.mark_failed(email)

        self.assertIsNotNone(self._wait_for_email(subject, self.config.failed_folder))

    def test_reply_success(self):
        subject = self._subject("reply-success")
        reply_subject = f"Re: {subject}"
        self.addCleanup(self._clean_emails, subject, reply_subject)
        email = self._seed_email(subject)
        appointment = Appointment(patient_name="Ana", study="Laboratorio")

        with self._client() as client:
            client.reply_success(email, appointment)

        reply = self._wait_for_email(reply_subject, self.config.imap["folder"])
        self.assertIsNotNone(reply)
        self.assertIn("agregado correctamente", reply.body)

    def test_reply_failed(self):
        subject = self._subject("reply-failed")
        reply_subject = f"Re: {subject}"
        self.addCleanup(self._clean_emails, subject, reply_subject)
        email = self._seed_email(subject)

        with self._client() as client:
            client.reply_failed(email, "No contiene fecha")

        reply = self._wait_for_email(reply_subject, self.config.imap["folder"])
        self.assertIsNotNone(reply)
        self.assertIn("No contiene fecha", reply.body)

    def _seed_email(self, subject):
        self._client().send(
            self.config.imap["username"],
            subject,
            "Correo de prueba de integracion.",
        )
        email = self._wait_for_email(subject, self.config.imap["folder"])
        self.assertIsNotNone(email, f"El correo {subject} no fue recibido")
        return email

    def _clean_emails(self, *subjects):
        subjects = set(subjects)
        test_sender = self.config.smtp["username"].lower()
        folders = {
            self.config.imap["folder"],
            self.config.processed_folder,
            self.config.failed_folder,
        }
        for folder in folders:
            for subject in subjects:
                client = self._client(
                    folder=folder,
                    search=f'HEADER Subject "{subject}"',
                )
                try:
                    with client:
                        for email in client.fetch(100):
                            if (
                                email.subject == subject
                                and email.sender.lower() == test_sender
                            ):
                                client.delete(email)
                except Exception:
                    # Cleanup must not hide the original test failure.
                    continue

    def _wait_for_email(self, subject, folder, search="ALL"):
        deadline = time.monotonic() + int(
            os.getenv("EMAIL_INTEGRATION_TIMEOUT_SECONDS", "60")
        )
        while time.monotonic() < deadline:
            with self._client(folder=folder, search=search) as client:
                email = next(
                    (mail for mail in client.fetch(100) if mail.subject == subject),
                    None,
                )
            if email:
                return email
            time.sleep(2)
        return None

    def _client(self, folder=None, search=None):
        imap = dict(self.config.imap)
        if folder is not None:
            imap["folder"] = folder
        if search is not None:
            imap["search"] = search
        return EmailClient(
            imap,
            self.config.smtp,
            self.config.processed_folder,
            self.config.failed_folder,
            self.config.allowed_senders,
        )

    @staticmethod
    def _subject(test_name):
        return f"[integration {test_name}] {uuid.uuid4()}"


if __name__ == "__main__":
    unittest.main()
