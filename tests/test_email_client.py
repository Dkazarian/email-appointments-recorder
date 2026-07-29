import imaplib
import unittest
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
SMTP = {"username": "smtp-user"}


def client() -> EmailClient:
    return EmailClient(IMAP, SMTP, "Processed", "Failed")


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
            b"Reply-To: Replies <reply@example.com>\r\n"
            b"Subject: =?utf-8?b?SG9sYQ==?=\r\n"
            b"Message-ID: <message-1>\r\n"
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
            [EmailItem("101", "Hola", "alice@example.com", "reply@example.com", "<message-1>", "<previous>", "Hello\n\nworld")],
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
