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

import json

from .utils import printable_phone_number


class MissingRecipientException(Exception):
    pass


class Message(object):  # pylint: disable=too-many-instance-attributes
    def __init__(self, json_dict=None):
        self.local_user = None
        self.recipient = None
        self.sender = None
        self.timestamp = None
        self.received_at = None
        self.body = None

        self.not_yet_sent = None

        if json_dict:
            for k in json_dict:
                setattr(self, k, json_dict[k])

        if self.recipient:
            self.recipient_printable = printable_phone_number(self.recipient)


    def _get_arrow(self):
        return '&larr;' if self.direction == 'in' else '&rarr;'
    arrow = property(_get_arrow)


    def _get_direction(self):
        if self.recipient:
            return 'out'
        else:
            return 'in'
    direction = property(_get_direction)


    def to_bytes(self):
        if not self.recipient:
            raise MissingRecipientException()

        msg_str = self.recipient + ":" + (self.body or '')
        return msg_str.encode('utf-8')


    def to_json(self):
        d = {}
        for k in ('local_user', 'recipient', 'sender', 'timestamp',
                  'received_at', 'body'):
            v = getattr(self, k, None)
            if v is not None:
                d[k] = v
        return d


    def to_json_str(self):
        d = self.to_json()
        return json.dumps(d)


    def __str__(self):
        return self.to_json_str()
