'''

Copyright 2017 Ewan Mellor

Changes authored by Hadi Esiely:
Copyright 2018 The Johns Hopkins University Applied Physics Laboratory LLC.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
contributors may be used to endorse or promote products derived from this
software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''

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


def rm_f(filename):
    try:
        os.remove(filename)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


def utcnow_str():
    return datetime.utcnow().isoformat('T')


def timestamp_filename(ts, ext):
    return '%s.%s' % (ts.replace(':', '.'), ext)
