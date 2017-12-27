'''

Copyright 2017 Hadi Esiely

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
import logging
import os
import os.path
import shutil

from enum import Enum

from .message import Message
from .utils import mkdir_p, normalize_phone_number, timestamp_filename, \
    utcnow_str


MAILBOXES_ROOT = '/var/opt/pr-holonet/mailboxes'


# Will be overridden by app.py for non-Gunicorn builds.
mailboxes_root = MAILBOXES_ROOT

_logger = logging.getLogger('holonet.mailboxes')


class MailboxKind(Enum):  # pylint: disable=too-few-public-methods
    thread = 1  # A thread of messages exchanged between two people
    outbox = 2  # Messages waiting to be sent
    inbox = 3  # Messages waiting to be read


def list_recipients(local_user):
    threadboxes_path = _path_of_threadboxes(local_user)
    if not os.path.exists(threadboxes_path):
        return []

    try:
        return sorted([d for d in os.listdir(threadboxes_path)
                       if not d.startswith('.')])
    except Exception as err:
        _logger.error('Error: failed to list %s even though it exists!  %s',
                      threadboxes_path, err)
        return []


def get_thread(local_user, recipient):
    threadbox_path = _path_of_threadbox(local_user, recipient)
    return _read_mailbox_sorted(threadbox_path, check_outbox=True)


def delete_thread(local_user, recipient):
    threadbox_path = _path_of_threadbox(local_user, recipient)
    try:
        shutil.rmtree(threadbox_path)
    except Exception as err:
        _logger.error('Cannot delete %s!  %s', threadbox_path, err)


def queue_message_send(local_user, recipient_, body):
    recipient = normalize_phone_number(recipient_)
    if not recipient:
        _logger.error('Refusing to send message to invalid phone number %s',
                      recipient_)

    threadbox_path = _path_of_threadbox(local_user, recipient)
    outbox_path = _path_of_mailbox(MailboxKind.outbox)

    now = utcnow_str()

    msg = Message()
    msg.local_user = local_user
    msg.recipient = recipient
    msg.timestamp = now
    msg.body = body

    msg_str = msg.to_json_str()

    fname = timestamp_filename(now, 'json')
    thread_path = os.path.join(threadbox_path, fname)
    outbox_path = os.path.join(outbox_path, fname)

    _write_file(outbox_path, msg_str)
    _write_file(thread_path, msg_str)


def read_outbox():
    """
    Returns: messages in the outbox, sorted chronologically.
    """
    outbox_path = _path_of_mailbox(MailboxKind.outbox)
    return _read_mailbox_sorted(outbox_path)


def remove_from_outbox(fname):
    _remove_from_mailbox(fname, MailboxKind.outbox)


def _read_mailbox_sorted(mailbox_path, check_outbox=False):
    """
    Returns: messages in the given mailbox, sorted chronologically.
    """
    messages = _read_mailbox(mailbox_path)

    if check_outbox:
        outbox_path = _path_of_mailbox(MailboxKind.outbox)
        outbox_contents = _read_mailbox(outbox_path)

        for msg in messages.values():
            if msg.filename in outbox_contents:
                msg.not_yet_sent = True

    result = []
    for fname in sorted(messages.keys()):
        result.append(messages[fname])
    return result


def _read_mailbox(mailbox_path):
    """
    Returns: dict where the key is the filename for the message, and the
    value is a Message instance.
    """
    if not os.path.exists(mailbox_path):
        return {}

    try:
        filenames = [f for f in os.listdir(mailbox_path)
                     if f.endswith(".json")]

        result = {}
        for filename in filenames:
            path = os.path.join(mailbox_path, filename)
            try:
                msg = _read_message(path)
                msg.filename = filename
                result[filename] = msg
            except Exception as err:
                _logger.error('Failed to read %s!  %s', path, err)
        return result
    except Exception as err:
        _logger.error('Failed to list %s even though it exists!  %s',
                      mailbox_path, err)


def save_message_to_inbox(data):
    inbox_path = _path_of_mailbox(MailboxKind.inbox)
    now = utcnow_str()

    fname = timestamp_filename(now, 'bin')
    inbox_file_path = os.path.join(inbox_path, fname)
    _write_file(inbox_file_path, data)


def accept_all_inbox_messages():
    msgs = read_inbox()

    result = []
    for msg in msgs:
        msg_filename = msg['filename']
        msg_data = msg['data']

        (sender, body) = msg_data.split(':', 1)
        now = utcnow_str()
        local_user = 'local'
        sender = sender
        timestamp = now
        received_at = now
        body = body

        new_msg = _accept_message(local_user, sender, timestamp, received_at,
                                  body)
        _remove_from_mailbox(msg_filename, MailboxKind.inbox)
        result.append(new_msg)

    return result


def read_inbox():
    """
    Returns: dict list where the dict contains 'filename' and 'data'.
    """
    inbox_path = _path_of_mailbox(MailboxKind.inbox)

    if not os.path.exists(inbox_path):
        return []

    try:
        infiles = [f for f in os.listdir(inbox_path)
                   if f.endswith(".bin")]

        result = []
        for filename in sorted(infiles):
            path = os.path.join(inbox_path, filename)
            try:
                data = _read_bin(path)
                result.append({
                    'filename': filename,
                    'data': data,
                })
            except Exception as err:
                _logger.error('Failed to read %s!  %s', path, err)
        return result
    except Exception as err:
        _logger.error('Failed to list %s even though it exists!  %s',
                      inbox_path, err)
        return []


def _accept_message(local_user, sender, timestamp, received_at, body):
    threadbox_path = _path_of_threadbox(local_user, sender)

    msg = Message()
    msg.local_user = local_user
    msg.sender = sender
    msg.timestamp = timestamp
    msg.received_at = received_at
    msg.body = body

    msg_str = msg.to_json_str()

    fname = timestamp_filename(received_at, 'json')
    thread_path = os.path.join(threadbox_path, fname)
    _write_file(thread_path, msg_str)

    return msg


def _remove_from_mailbox(filename, kind):
    mailbox_path = _path_of_mailbox(kind)
    path = os.path.join(mailbox_path, filename)
    try:
        os.remove(path)
    except Exception as err:
        _logger.error('Failed to remove %s!  %s', path, err)


def _read_bin(path):
    with open(path, 'r') as f:
        return f.read()


def _read_message(path):
    msg_json = _read_json(path)
    return Message(msg_json)


def _read_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def _write_file(path, data):
    mkdir_p(os.path.dirname(path))

    mode = 'w' if isinstance(data, str) else 'wb'
    tmpfile = '%s.tmp' % path
    with open(tmpfile, mode) as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmpfile, path)


def _path_of_mailbox(kind):
    kind_label = _label_of_kind(kind)
    return os.path.join(mailboxes_root, kind_label)

def _path_of_threadboxes(local_user):
    return os.path.join(mailboxes_root, local_user, 'thread')

def _path_of_threadbox(local_user, remote_user):
    return os.path.join(_path_of_threadboxes(local_user), remote_user)


def _label_of_kind(kind):
    kinds = {
        MailboxKind.thread: 'thread',
        MailboxKind.outbox: 'outbox',
        MailboxKind.inbox: 'inbox',
    }
    return kinds[kind]
