from datetime import datetime
import errno
import os

import phonenumbers


def do_callback(handler, f, *args):
    cb = getattr(handler, f.__name__, None)
    if cb is None:
        return None
    return cb(*args)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as err:
        if err.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def normalize_phone_number(s):
    if not s:
        return None

    # Note that we're assuming USA phone numbers here, unless the user
    # starts the number with a +.
    country = None if s[0] == '+' else 'US'
    no = phonenumbers.parse(s, country)
    if not phonenumbers.is_valid_number(no):
        return None
    else:
        return phonenumbers.format_number(
            no, phonenumbers.PhoneNumberFormat.E164)


def printable_phone_number(s):
    if not s:
        return ''

    # Note that we're assuming USA here, but this shouldn't matter, because
    # s should already be in E.164 format.
    no = phonenumbers.parse(s, 'US')
    if not phonenumbers.is_valid_number(no):
        return s

    # We're checking for +1 here, but this simply means that non-US numbers
    # will have the international prefix.
    fmt = (phonenumbers.PhoneNumberFormat.NATIONAL if no.country_code == 1
           else phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    return phonenumbers.format_number(no, fmt)


def utcnow_str():
    return datetime.utcnow().isoformat('T')


def timestamp_filename(ts, ext):
    return '%s.%s' % (ts.replace(':', '.'), ext)
