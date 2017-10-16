import asyncio
import traceback
from threading import Thread

from holonet import mailboxes, rockblock


_event_loop = None
_thread = None
_queue_manager = None


class SendFailureException(Exception):
    pass


def start():
    global _event_loop
    global _thread
    global _queue_manager

    _queue_manager = QueueManager()

    _event_loop = asyncio.new_event_loop()
    _thread = Thread(target=_event_loop.run_forever)
    _thread.daemon = True
    _thread.start()



def check_for_messages():
    _event_loop.call_soon_threadsafe(_check_for_messages_background)

def _check_for_messages_background():
    _queue_manager.check_for_messages()

def check_outbox():
    _event_loop.call_soon_threadsafe(_check_outbox_background)

def _check_outbox_background():
    _queue_manager.check_outbox()

def get_messages():
    _event_loop.call_soon_threadsafe(_get_messages_background)

def _get_messages_background():
    _queue_manager.get_messages()


class QueueManager(rockblock.RockBlockProtocol):
    def __init__(self):
        self.rockblock = rockblock.RockBlock("/dev/ttyUSB0", self)

        self.send_status = None


    def check_for_messages(self):
        try:
            self._try_to_check_for_messages()
        except Exception as err:
            print('Error: failed to check for messages: %s' % err)
            traceback.print_exc()

    def _try_to_check_for_messages(self):
        # TODO: Call RockBLOCK to check whether any messages are pending, and
        # update the locally cached flag for the has_messages status.
        # This is a no-op right now because we have not implemented the ring
        # line.
        print('RockBLOCK: would check for pending messages')
        _ = self
        # time.sleep(4)

    def get_messages(self):
        self.check_for_messages()

        # TODO: Check locally cached flag for RockBLOCK has_messages status.
        # This is a no-op right now because we have not implemented the ring
        # line.
        has_messages = True
        if has_messages:
            try:
                self._try_to_get_messages()
            except Exception as err:
                print('Error: failed to get messages: %s' % err)
                traceback.print_exc()

        try:
            mailboxes.accept_all_inbox_messages()
        except Exception as err:
            print('Error: failed to check for messages: %s' % err)
            traceback.print_exc()


    def _try_to_get_messages(self):
        # We get calls to rockBlockRxReceived during the call below for any
        # messages that were waiting for us.
        print("Checking for messages")
        self.rockblock.messageCheck()


    def rockBlockRxReceived(self, _mtmsn, data):
        _ = self
        print("Received %s" % data)
        mailboxes.save_message_to_inbox(data)


    def check_outbox(self):
        outbox = mailboxes.read_outbox()

        for msg in outbox:
            self._send_message(msg)


    def _send_message(self, msg):
        try:
            print("Trying to send %s" % msg)
            self._try_to_send_message(msg)
            mailboxes.remove_from_outbox(msg['filename'])
            print("Successfully sent and removed %s" % msg)
        except Exception as err:
            print('Error: Tried to send message %s, but failed: %s' %
                  (msg['filename'], err))
            traceback.print_exc()
            # TODO: We're currently just leaving the message, so we'll retry it
            # forever.  Give up at some point?


    def _try_to_send_message(self, msg):
        print('RockBLOCK: sending %s' % msg)
        # We get calls to rockBlockTxSuccess / rockBlockTxFailed during the call
        # below.  We use self.send_status as a hack to unpick the callback.
        self.send_status = None
        self.rockblock.send_message(msg['recipient'], msg['body'])
        assert self.send_status is not None
        if not self.send_status:
            print('RockBLOCK: sending %s failed.' % msg)
            raise SendFailureException()


    def rockBlockTxFailed(self):
        self.send_status = False


    def rockBlockTxSuccess(self, momsn):
        print('RockBLOCK: TxSuccess.  Message ID: %s' % momsn)
        self.send_status = True


    def rockBlockRxStarted(self):
        print("Rxstarted")

    def rockBlockRxFailed(self):
        print("RxFailed")
