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
