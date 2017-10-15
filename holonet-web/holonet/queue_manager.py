import asyncio
import time
from threading import Thread

from holonet import mailboxes


_event_loop = None
_thread = None


def start():
    global _event_loop
    global _thread

    _event_loop = asyncio.new_event_loop()
    _thread = Thread(target=_event_loop.run_forever)
    _thread.daemon = True
    _thread.start()


def check_for_messages():
    _event_loop.call_soon_threadsafe(_check_for_messages_background)

def _check_for_messages_background():
    try:
        _try_to_check_for_messages()
    except Exception as err:
        print('Error: failed to check for messages: %s' % err)

def _try_to_check_for_messages():
    # TODO: Call RockBLOCK to check whether any messages are pending, and
    # update the locally cached flag for the has_messages status.
    print('RockBLOCK: would check for pending messages')
    time.sleep(4)


def get_messages():
    _event_loop.call_soon_threadsafe(_get_messages_background)

def _get_messages_background():
    check_for_messages()

    # TODO: Check locally cached flag for RockBLOCK has_messages status.
    has_messages = True
    if has_messages:
        try:
            _try_to_get_messages()
        except Exception as err:
            print('Error: failed to get messages: %s' % err)

    try:
        mailboxes.accept_all_inbox_messages()
    except Exception as err:
        print('Error: failed to check for messages: %s' % err)


def _try_to_get_messages():
    # TODO: Call RockBLOCK to get messages.
    print('RockBLOCK: would get messages')
    time.sleep(10)
    messages = []

    for msg_data in messages:
        mailboxes.save_message_to_inbox(msg_data)

    # TODO: Do we need a call to RockBLOCK to say that we've accepted
    # messages / turn off the message-waiting flag?


def check_outbox():
    _event_loop.call_soon_threadsafe(_check_outbox_background)

def _check_outbox_background():
    outbox = mailboxes.read_outbox()

    for msg in outbox:
        _send_message(msg)


def _send_message(msg):
    try:
        _try_to_send_message(msg)
        mailboxes.remove_from_outbox(msg['filename'])
    except Exception as err:
        print('Error: Tried to send message %s, but failed: %s' %
              (msg['filename'], err))
        # TODO: We're currently just leaving the message, so we'll retry it
        # forever.  Give up at some point?


def _try_to_send_message(msg):
    # TODO: Call RockBLOCK with the message.
    # TODO: Throw an exception if the send failed.
    print('RockBLOCK: would send %s' % msg)
    time.sleep(40)
