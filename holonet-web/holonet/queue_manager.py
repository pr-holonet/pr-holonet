import asyncio
import logging
import traceback
from threading import Thread

from serial import serialutil

from holonet import mailboxes, rockblock


last_known_signal_status = False
last_known_signal_strength = 0
last_known_rockblock_status = 'Unknown'
last_txfailed_mo_status = 0
rockblock_serial_identifier = None

_logger = logging.getLogger('holonet.queue_manager')

_event_loop = None
_thread = None
_queue_manager = None


class SendFailureException(Exception):
    pass


def start(device=None):
    global _event_loop
    global _thread
    global _queue_manager

    _queue_manager = QueueManager(device=device)

    _event_loop = asyncio.new_event_loop()
    _thread = Thread(target=_event_loop.run_forever)
    _thread.daemon = True
    _thread.start()

    _event_loop.call_soon_threadsafe(_queue_manager.get_serial_identifier)


def check_for_messages():
    _event_loop.call_soon_threadsafe(_queue_manager.check_for_messages)

def check_outbox():
    _event_loop.call_soon_threadsafe(_queue_manager.check_outbox)

def get_messages():
    _event_loop.call_soon_threadsafe(_queue_manager.get_messages)

def request_signal_strength():
    _event_loop.call_soon_threadsafe(_queue_manager.request_signal_strength)


class QueueManager(rockblock.RockBlockProtocol):
    def __init__(self, device):
        global last_known_rockblock_status

        self.send_status = None

        try:
            if device is None:
                devices = rockblock.RockBlock.listPorts()
                if not devices:
                    _logger.error(
                        'Cannot find RockBLOCK (or any working serial '
                        'connections)!  Will muddle on without it.')
                    self.rockblock = None
                    last_known_rockblock_status = 'Missing'
                    return
                device = devices[0]
            self.rockblock = rockblock.RockBlock(device, self)
            last_known_rockblock_status = 'Installed'
        except serialutil.SerialException as err:
            _logger.error(
                'Failed to initialize RockBLOCK!  Will muddle on without it.  '
                '%s', err)
            self.rockblock = None
            last_known_rockblock_status = 'Missing'
        except:  # pylint: disable=bare-except
            _logger.error(
                'Failed to initialize RockBLOCK!  Will muddle on without it.')
            traceback.print_exc()
            self.rockblock = None
            last_known_rockblock_status = 'Broken'


    def get_serial_identifier(self):
        if self.rockblock is None:
            _logger.debug(
                'Cannot get serial identifier: we have no RockBLOCK.')
            return

        try:
            global rockblock_serial_identifier
            rockblock_serial_identifier = self.rockblock.getSerialIdentifier()
        except Exception as err:
            _logger.error('Failed to get RockBLOCK serial identifier: %s', err)
            traceback.print_exc()


    def check_for_messages(self):
        try:
            self._try_to_check_for_messages()
        except Exception as err:
            _logger.warning('Failed to check for messages: %s', err)

    def _try_to_check_for_messages(self):
        # TODO: Call RockBLOCK to check whether any messages are pending, and
        # update the locally cached flag for the has_messages status.
        # This is a no-op right now because we have not implemented the ring
        # line.
        _logger.debug('RockBLOCK: would check for pending messages.')
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
                _logger.warning('Failed to get messages: %s', err)
                traceback.print_exc()

        try:
            mailboxes.accept_all_inbox_messages()
        except Exception as err:
            _logger.error('Failed to accept messages: %s', err)
            traceback.print_exc()


    def _try_to_get_messages(self):
        if self.rockblock is None:
            _logger.debug('Cannot get messages: we have no RockBLOCK.')
            return

        # We get calls to rockBlockRxReceived during the call below for any
        # messages that were waiting for us.
        _logger.debug('Checking for messages.')
        self.rockblock.messageCheck()


    def rockBlockRxReceived(self, _mtmsn, data):
        _ = self
        _logger.debug('RockBLOCK: Received data of length %s.', len(data))
        mailboxes.save_message_to_inbox(data)


    def check_outbox(self):
        outbox = mailboxes.read_outbox()
        for msg in outbox:
            self._send_message(msg)


    def _send_message(self, msg):
        if self.rockblock is None:
            _logger.info('Cannot send message: we have no RockBLOCK.  %s', msg)
            return

        try:
            self._try_to_send_message(msg)
            mailboxes.remove_from_outbox(msg.filename)
            _logger.debug('Successfully sent and removed %s.', msg.filename)
        except Exception as err:
            _logger.warning('Tried to send message %s, but failed: %s',
                            msg.filename, err)
            # TODO: We're currently just leaving the message, so we'll retry it
            # forever.  Give up at some point?


    def _try_to_send_message(self, msg):
        _logger.debug('RockBLOCK: sending %s.', msg.filename)

        msg_bytes = msg.to_bytes()
        # We get calls to rockBlockTxSuccess / rockBlockTxFailed during the
        # call below.  We use self.send_status as a hack to unpick the
        # callback.
        self.send_status = None
        self.rockblock.sendMessage(msg_bytes)
        assert self.send_status is not None
        if not self.send_status:
            _logger.warning('RockBLOCK: sending %s failed.', msg)
            raise SendFailureException()


    def rockBlockTxFailed(self, moStatus):
        global last_txfailed_mo_status
        last_txfailed_mo_status = moStatus
        self.send_status = False


    def rockBlockTxSuccess(self, momsn):
        _logger.debug('RockBLOCK: TxSuccess.  Message ID: %s.', momsn)
        self.send_status = True


    def rockBlockRxStarted(self):
        _logger.debug('RockBLOCK: RxStarted.')

    def rockBlockRxFailed(self):
        _logger.debug('RockBLOCK: RxFailed.')


    def request_signal_strength(self):
        if self.rockblock is None:
            _logger.debug(
                'Cannot request signal strength: we have no RockBLOCK.')
            return

        # This triggers a callback to rockBlockSignalUpdate (assuming it
        # succeeds).
        self.rockblock.wait_for_good_signal()

    def rockBlockSignalUpdate(self, signal):
        global last_known_signal_status
        global last_known_signal_strength

        _logger.info('RockBLOCK: signal strength = %s.', signal)
        last_known_signal_strength = signal
        if signal < rockblock.SIGNAL_THRESHOLD:
            _logger.warning('RockBLOCK: No signal.')
            last_known_signal_status = False
        else:
            last = last_known_signal_status
            last_known_signal_status = True
            if last:
                return
            _logger.debug(
                'RockBLOCK: signal is back.  Checking for outbound messages.')
            check_outbox()
