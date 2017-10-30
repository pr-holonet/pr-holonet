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


def utcnow_str():
    return datetime.utcnow().isoformat('T')


def timestamp_filename(ts, ext):
    return '%s.%s' % (ts.replace(':', '.'), ext)
