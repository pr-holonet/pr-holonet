from unittest import TestCase

from holonet.utils import normalize_phone_number, printable_phone_number


class TestMessage(TestCase):
    def test_normalize_phone_number(self):
        def t(n, e):
            r = normalize_phone_number(n)
            self.assertEqual(r, e)

        t('4158008000', '+14158008000')
        t('4158008000', '+14158008000')
        t('415-800-8000', '+14158008000')
        t('1-415-800-8000', '+14158008000')
        t('(415) 800-8000', '+14158008000')
        t('+1 415 800-8000', '+14158008000')
        t('+44 151 800-8000', '+441518008000')


    def test_printable_phone_number(self):
        def t(n, e):
            r = printable_phone_number(n)
            self.assertEqual(r, e)

        t('+14158008000', '(415) 800-8000')
        t('+441518008000', '+44 151 800 8000')
        t('+10008008000', '+10008008000')
