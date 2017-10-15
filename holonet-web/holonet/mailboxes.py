import json
import os
import os.path
import shutil

from enum import Enum

from .utils import mkdir_p, timestamp_filename, utcnow_str


# MAILBOXES_ROOT = '/var/opt/pr-holonet/mailboxes'
MAILBOXES_ROOT = '/Users/ewan/pr-holonet/mailboxes'


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
        print('Error: failed to list %s even though it exists!  %s' %
              (threadboxes_path, err))
        return []


def get_thread(local_user, recipient):
    threadbox_path = _path_of_threadbox(local_user, recipient)
    return _read_mailbox_sorted(threadbox_path, check_outbox=True)


def delete_thread(local_user, recipient):
    threadbox_path = _path_of_threadbox(local_user, recipient)
    try:
        shutil.rmtree(threadbox_path)
    except Exception as err:
        print('Cannot delete %s!  %s' % (threadbox_path, err))


def queue_message_send(local_user, recipient, body):
    threadbox_path = _path_of_threadbox(local_user, recipient)
    outbox_path = _path_of_mailbox(MailboxKind.outbox)

    now = utcnow_str()

    message = {
        'local_user': local_user,
        'recipient': recipient,
        'timestamp': now,
        'body': body,
    }

    message_str = json.dumps(message)

    fname = timestamp_filename(now, 'json')
    thread_path = os.path.join(threadbox_path, fname)
    outbox_path = os.path.join(outbox_path, fname)

    _write_file(outbox_path, message_str)
    _write_file(thread_path, message_str)


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
            if msg['filename'] in outbox_contents:
                msg['not_yet_sent'] = True

    result = []
    for fname in sorted(messages.keys()):
        result.append(messages[fname])
    return result


def _read_mailbox(mailbox_path):
    """
    Returns: dict where the key is the filename for the message, and the
    value is the message dict.
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
                msg = _read_json(path)
                if msg.get('recipient'):
                    msg['direction'] = 'out'
                else:
                    msg['direction'] = 'in'
                msg['filename'] = filename
                result[filename] = msg
            except Exception as err:
                print('Error: failed to read %s!  %s' % (path, err))
        return result
    except Exception as err:
        print('Error: failed to list %s even though it exists!  %s' %
              (mailbox_path, err))


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

        # TODO: Parse the received message
        now = utcnow_str()
        local_user = 'local'
        sender = 'aperson'
        timestamp = now
        received_at = now
        body = msg_data

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
                print('Error: failed to read %s!  %s' % (path, err))
        return result
    except Exception as err:
        print('Error: failed to list %s even though it exists!  %s' %
              (inbox_path, err))
        return []


def _accept_message(local_user, sender, timestamp, received_at, body):
    threadbox_path = _path_of_threadbox(local_user, sender)

    message = {
        'local_user': local_user,
        'sender': sender,
        'timestamp': timestamp,
        'received_at': received_at,
        'body': body,
    }

    message_str = json.dumps(message)

    fname = '%s.json' % received_at
    thread_path = os.path.join(threadbox_path, fname)
    _write_file(thread_path, message_str)

    return message


def _remove_from_mailbox(filename, kind):
    mailbox_path = _path_of_mailbox(kind)
    path = os.path.join(mailbox_path, filename)
    try:
        os.remove(path)
    except Exception as err:
        print('Error: failed to remove %s!  %s' % (path, err))


def _read_bin(path):
    with open(path, 'r') as f:
        return f.read()


def _read_json(path):
    with open(path, 'r') as f:
        return json.load(f)


def _write_file(path, data):
    mkdir_p(os.path.dirname(path))

    tmpfile = '%s.tmp' % path
    with open(tmpfile, 'w') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmpfile, path)


def _path_of_mailbox(kind):
    kind_label = _label_of_kind(kind)
    return os.path.join(MAILBOXES_ROOT, kind_label)

def _path_of_threadboxes(local_user):
    return os.path.join(MAILBOXES_ROOT, local_user, 'thread')

def _path_of_threadbox(local_user, remote_user):
    return os.path.join(_path_of_threadboxes(local_user), remote_user)


def _label_of_kind(kind):
    kinds = {
        MailboxKind.thread: 'thread',
        MailboxKind.outbox: 'outbox',
        MailboxKind.inbox: 'inbox',
    }
    return kinds[kind]