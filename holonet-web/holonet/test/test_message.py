from unittest import TestCase

from holonet.message import Message, MissingRecipientException


class TestMessage(TestCase):
    def test_to_bytes(self):
        def t(m, e):
            r = m.to_bytes()
            self.assertEqual(r, e)

        m = Message()
        m.recipient = '18008008000'
        t(m, b'18008008000:')

        m = Message()
        m.recipient = '18008008000'
        m.body = 'Hi'
        t(m, b'18008008000:Hi')


    def test_to_bytes_missing_recipient(self):
        m = Message()
        with self.assertRaises(MissingRecipientException):
            m.to_bytes()
