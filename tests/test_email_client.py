import imaplib
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, call, patch

from app.email_client import EmailClient, EmailItem


IMAP = {
    "host": "imap.example.test",
    "port": 993,
    "username": "imap-user",
    "password": "secret",
    "folder": "INBOX",
    "search": "UNSEEN",
}
SMTP = {
    "host": "smtp.example.test",
    "port": 465,
    "username": "smtp-user",
    "password": "smtp-secret",
}


def client(allowed_senders=None) -> EmailClient:
    return EmailClient(IMAP, SMTP, "Processed", "Failed", allowed_senders)


class EmailClientTests(unittest.TestCase):
    @patch("app.email_client.imaplib.IMAP4_SSL")
    def test_context_manager_connects_and_disconnects(self, imap_class):
        imap = imap_class.return_value

        with client() as email_client:
            self.assertIs(email_client._imap, imap)

        imap_class.assert_called_once_with("imap.example.test", 993)
        imap.login.assert_called_once_with("imap-user", "secret")
        imap.select.assert_called_once_with("INBOX")
        imap.close.assert_called_once_with()
        imap.logout.assert_called_once_with()
        self.assertIsNone(email_client._imap)

    def test_operations_require_a_connection(self):
        with self.assertRaisesRegex(RuntimeError, "no esta conectado"):
            client().fetch(1)

    def test_fetch_parses_headers_and_prefers_plain_text(self):
        email_client = client()
        imap = Mock()
        email_client._imap = imap
        raw = (
            b"From: Alice <alice@example.com>\r\n"
            b"To: Ernesto <ernesto@example.com>, team@example.com\r\n"
            b"Cc: copy@example.com\r\n"
            b"Date: Mon, 24 Mar 2025 15:55:00 -0300\r\n"
            b"Reply-To: Replies <reply@example.com>\r\n"
            b"Subject: =?utf-8?b?SG9sYQ==?=\r\n"
            b"Message-ID: <message-1@example.com>\r\n"
            b"References: <previous>\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            b"Hello\n\n\nworld\n"
        )
        imap.uid.side_effect = [
            ("OK", [b"101 102"]),
            ("OK", [(b"header", raw)]),
            ("NO", []),
        ]

        result = email_client.fetch(2)

        self.assertEqual(
            result,
            [EmailItem(
                uid="101",
                url="https://mail.google.com/mail/u/0/#search/rfc822msgid%3Amessage-1%40example.com",
                sender="alice@example.com",
                reply_to="reply@example.com",
                recipients=["ernesto@example.com", "team@example.com", "copy@example.com"],
                subject="Hola",
                sent_at=datetime(2025, 3, 24, 15, 55, tzinfo=timezone(timedelta(hours=-3))),
                body="Hello\n\nworld",
            )],
        )
        self.assertEqual(imap.uid.call_args_list[0], call("search", None, "UNSEEN"))

    def test_fetch_uses_html_as_fallback_and_honors_limit(self):
        email_client = client()
        imap = Mock()
        email_client._imap = imap
        raw = b"From: sender@example.com\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>Hello</p><br>world"
        imap.uid.side_effect = [("OK", [b"1 2"]), ("OK", [(b"header", raw)])]

        result = email_client.fetch(1)

        self.assertEqual(result[0].body, "Hello\nworld")
        self.assertEqual(imap.uid.call_count, 2)

    def test_fetch_ignores_senders_outside_whitelist(self):
        email_client = client({"allowed@example.com"})
        imap = Mock()
        email_client._imap = imap
        allowed = b"From: allowed@example.com\r\n\r\nAllowed"
        blocked = b"From: blocked@example.com\r\n\r\nBlocked"
        imap.uid.side_effect = [
            ("OK", [b"1 2"]),
            ("OK", [(b"header", allowed)]),
            ("OK", [(b"header", blocked)]),
        ]

        result = email_client.fetch(2)

        self.assertEqual([mail.sender for mail in result], ["allowed@example.com"])

    def test_fetch_strips_gmail_quoted_conversation_from_body(self):
        email_client = client()
        imap = Mock()
        email_client._imap = imap
        raw = (
            b"From: sender@example.com\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            b"hello too\n\n"
            b"El vie, 5 jun 2026 a las 16:13, someone@mail escribi\xc3\xb3:\n"
            b"hello\n"
        )
        imap.uid.side_effect = [("OK", [b"1"]), ("OK", [(b"header", raw)])]

        result = email_client.fetch(1)

        self.assertEqual(result[0].body, "hello too")

    def test_fetch_strips_common_quoted_reply_formats_from_body(self):
        examples = [
            "new reply\n\nOn Fri, Jun 5, 2026, someone@mail wrote:\nold reply",
            "new reply\n\n-----Original Message-----\nold reply",
            "new reply\n\n-----Mensaje original-----\nold reply",
            "new reply\n\nBegin forwarded message:\nold reply",
            "new reply\n\nInicio del mensaje reenviado:\nold reply",
            "new reply\n\nDe: old@example.com\nEnviado el: 5/6/2026\nold reply",
            "new reply\n\nFrom: old@example.com\nSent: June 5, 2026\nold reply",
            "new reply\n\n______________\nold reply",
            "new reply\n\n> old reply\n> older reply",
        ]

        for body in examples:
            with self.subTest(body=body):
                email_client = client()
                imap = Mock()
                email_client._imap = imap
                raw = (
                    b"From: sender@example.com\r\n"
                    b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
                    + body.encode("utf-8")
                )
                imap.uid.side_effect = [("OK", [b"1"]), ("OK", [(b"header", raw)])]

                result = email_client.fetch(1)

                self.assertEqual(result[0].body, "new reply")

    def test_fetch_ignores_appended_files(self):
        email_client = client()
        imap = Mock()
        email_client._imap = imap
        raw = (
            b"From: sender@example.com\r\n"
            b"Content-Type: multipart/mixed; boundary=part\r\n\r\n"
            b"--part\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            b"Body\r\n"
            b"--part\r\n"
            b"Content-Type: application/pdf\r\n"
            b"Content-Disposition: attachment; filename=file.pdf\r\n\r\n"
            b"ignored file\r\n"
            b"--part--\r\n"
        )
        imap.uid.side_effect = [("OK", [b"1"]), ("OK", [(b"header", raw)])]

        result = email_client.fetch(1)

        self.assertEqual(result[0].body, "Body")

    def test_mark_seen(self):
        email_client = client()
        email_client._imap = Mock()

        email_client.mark_seen("42")

        email_client._imap.uid.assert_called_once_with("store", "42", "+FLAGS", r"(\Seen)")

    def test_mark_completed_marks_seen_and_moves_to_processed_folder(self):
        email_client = client()
        with patch.object(email_client, "mark_seen") as mark_seen, patch.object(email_client, "move") as move:
            email_client.mark_completed("42")

        mark_seen.assert_called_once_with("42")
        move.assert_called_once_with("42", "Processed")

    def test_mark_failed_accepts_email_item_and_moves_to_failed_folder(self):
        email_client = client()
        email = EmailItem(
            uid="42",
            url=None,
            sender="from@example.com",
            reply_to="from@example.com",
            recipients=[],
            subject="Subject",
            sent_at=None,
            body="Body",
        )
        with patch.object(email_client, "mark_seen") as mark_seen, patch.object(email_client, "move") as move:
            email_client.mark_failed(email)

        mark_seen.assert_called_once_with("42")
        move.assert_called_once_with("42", "Failed")

    @patch("app.email_client.smtplib.SMTP_SSL")
    def test_send_sends_plain_text_message(self, smtp_class):
        email_client = client()

        email_client.send("recipient@example.com", "Subject", "Body")

        smtp = smtp_class.return_value.__enter__.return_value
        smtp.login.assert_called_once_with("smtp-user", "smtp-secret")
        sent_message = smtp.send_message.call_args.args[0]
        self.assertEqual(sent_message["To"], "recipient@example.com")
        self.assertEqual(sent_message["Subject"], "Subject")
        self.assertTrue(sent_message["Date"])
        self.assertTrue(sent_message["Message-ID"])
        self.assertIn("Body", sent_message.get_content())

    def test_delete_marks_uid_deleted_and_expunges(self):
        email_client = client()
        email_client._imap = Mock()
        email_client._imap.uid.return_value = ("OK", [])

        email_client.delete("42")

        email_client._imap.uid.assert_called_once_with(
            "STORE", "42", "+FLAGS", r"(\Deleted)"
        )
        email_client._imap.expunge.assert_called_once_with()

    @patch("app.email_client.smtplib.SMTP_SSL")
    def test_reply_success_sends_confirmation_to_reply_to(self, smtp_class):
        email_client = client()
        email = EmailItem(
            uid="42",
            url=None,
            sender="sender@example.com",
            reply_to="reply@example.com",
            recipients=[],
            subject="Turno",
            sent_at=None,
            body="Body",
        )
        appointment = Mock(
            patient_name="Ernesto",
            study="Radiografia",
            clinic_or_professional="Clinica Rosa",
            date="24/3",
            time="15:55",
        )

        email_client.reply_success(email, appointment)

        smtp = smtp_class.return_value.__enter__.return_value
        smtp.login.assert_called_once_with("smtp-user", "smtp-secret")
        sent_message = smtp.send_message.call_args.args[0]
        self.assertEqual(sent_message["To"], "reply@example.com")
        self.assertEqual(sent_message["Subject"], "Re: Turno")
        self.assertIn("agregado correctamente", sent_message.get_content())

    @patch("app.email_client.smtplib.SMTP_SSL")
    def test_reply_failed_reports_error(self, smtp_class):
        email_client = client()
        email = EmailItem(
            uid="42",
            url=None,
            sender="sender@example.com",
            reply_to="",
            recipients=[],
            subject="Re: Turno",
            sent_at=None,
            body="Body",
        )

        email_client.reply_failed(email, "No contiene fecha")

        sent_message = smtp_class.return_value.__enter__.return_value.send_message.call_args.args[0]
        self.assertEqual(sent_message["To"], "sender@example.com")
        self.assertEqual(sent_message["Subject"], "Re: Turno")
        self.assertIn("No contiene fecha", sent_message.get_content())

    def test_move_uses_move_when_supported(self):
        email_client = client()
        imap = Mock()
        email_client._imap = imap
        imap.create.return_value = ("OK", [b""])
        imap.uid.return_value = ("OK", [b""])

        email_client.move("42", "Processed")

        self.assertEqual(imap.uid.call_args_list, [call("MOVE", "42", "Processed")])

    def test_move_falls_back_to_copy_delete_and_expunge(self):
        email_client = client()
        imap = Mock()
        email_client._imap = imap
        imap.create.return_value = ("NO", [b"already exists"])
        imap.uid.side_effect = [("NO", []), ("OK", []), ("OK", [])]

        email_client.move("42", "Processed")

        self.assertEqual(
            imap.uid.call_args_list,
            [
                call("MOVE", "42", "Processed"),
                call("COPY", "42", "Processed"),
                call("STORE", "42", "+FLAGS", r"(\Deleted)"),
            ],
        )
        imap.expunge.assert_called_once_with()

    def test_move_reconnects_once_for_retriable_abort(self):
        email_client = client()
        first_imap = Mock()
        second_imap = Mock()
        email_client._imap = first_imap
        first_imap.create.return_value = ("OK", [])
        first_imap.uid.side_effect = imaplib.IMAP4.abort("socket error")
        second_imap.create.return_value = ("OK", [])
        second_imap.uid.return_value = ("OK", [])

        with patch.object(email_client, "reconnect", side_effect=lambda: setattr(email_client, "_imap", second_imap)) as reconnect:
            email_client.move("42", "Processed")

        reconnect.assert_called_once_with()
        second_imap.uid.assert_called_once_with("MOVE", "42", "Processed")

    def test_disconnect_ignores_imap_errors(self):
        email_client = client()
        imap = Mock()
        email_client._imap = imap
        imap.close.side_effect = imaplib.IMAP4.error("closed")
        imap.logout.side_effect = imaplib.IMAP4.error("logged out")

        email_client._disconnect()

        self.assertIsNone(email_client._imap)


if __name__ == "__main__":
    unittest.main()
