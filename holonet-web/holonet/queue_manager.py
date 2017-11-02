import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from threading import Thread

from serial import serialutil

from holonet import holonetGPIO, mailboxes, rockblock

SIGNAL_CHECK_SECONDS = 60 * 5


last_known_signal_status = False
last_known_signal_strength = 0
last_known_signal_time = datetime.min
last_known_rockblock_status = 'Unknown'
last_txfailed_mo_status = 0
message_pending_senders = {}
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
    request_signal_strength()
    _event_loop.call_later(SIGNAL_CHECK_SECONDS, _check_signal)


def check_outbox():
    _event_loop.call_soon_threadsafe(_queue_manager.check_outbox)

def clear_message_pending(sender):
    if sender in message_pending_senders:
        del message_pending_senders[sender]
    led_status = bool(message_pending_senders)
    holonetGPIO.HolonetGPIO.set_led_message_pending(led_status)

def get_messages(ack_ring):
    _event_loop.call_soon_threadsafe(_queue_manager.get_messages, ack_ring)

def request_signal_strength():
    _event_loop.call_soon_threadsafe(_queue_manager.request_signal_strength)

def _check_signal():
    _event_loop.call_soon_threadsafe(_queue_manager.check_signal)
    _event_loop.call_later(SIGNAL_CHECK_SECONDS, _check_signal)


class QueueManager(rockblock.RockBlockProtocol,
                   holonetGPIO.HolonetGPIOProtocol):
    def __init__(self, device):
        global last_known_rockblock_status

        self.send_status = None

        self.gpio = holonetGPIO.HolonetGPIO(self)
        self.gpio.set_led_connection_status(holonetGPIO.BLUE)
        self.gpio.set_led_message_pending(False)

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
        except:  # noqa pylint: disable=bare-except
            _logger.error(
                'Failed to initialize RockBLOCK!  Will muddle on without it.')
            traceback.print_exc()
            self.rockblock = None
            last_known_rockblock_status = 'Broken'

        if self.rockblock is None:
            self.gpio.set_led_connection_status(holonetGPIO.RED)


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


    def get_messages(self, ack_ring):
        try:
            self._try_to_get_messages(ack_ring=ack_ring)
        except Exception as err:
            _logger.warning('Failed to get messages: %s', err)
            traceback.print_exc()

        try:
            msgs = mailboxes.accept_all_inbox_messages()
            if msgs:
                for msg in msgs:
                    message_pending_senders[msg.sender] = True
                self.gpio.set_led_message_pending(True)
        except Exception as err:
            _logger.error('Failed to accept messages: %s', err)
            traceback.print_exc()


    def _try_to_get_messages(self, ack_ring):
        if self.rockblock is None:
            _logger.debug('Cannot get messages: we have no RockBLOCK.')
            return

        # We get calls to rockBlockRxReceived during the call below for any
        # messages that were waiting for us.
        _logger.debug('Checking for messages.')
        self.rockblock.messageCheck(ack_ring=ack_ring)


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
        self.rockblock.requestSignalStrength()

    def rockBlockSignalUpdate(self, signal):
        global last_known_signal_status
        global last_known_signal_strength
        global last_known_signal_time

        _logger.info('RockBLOCK: signal strength = %s.', signal)
        last_known_signal_strength = signal
        last_known_signal_time = datetime.utcnow()
        if signal < rockblock.SIGNAL_THRESHOLD:
            _logger.warning('RockBLOCK: No signal.')
            last_known_signal_status = False
            self.gpio.set_led_connection_status(holonetGPIO.YELLOW)
        else:
            last = last_known_signal_status
            last_known_signal_status = True
            self.gpio.set_led_connection_status(holonetGPIO.GREEN)
            if last:
                return
            _logger.debug(
                'RockBLOCK: signal is back.  Checking for outbound messages.')
            check_outbox()


    def check_signal(self):
        global last_known_signal_time

        now = datetime.utcnow()
        then = last_known_signal_time + timedelta(seconds=SIGNAL_CHECK_SECONDS)
        if then < now:
            last_known_signal_time = now
            self.request_signal_strength()


    def holonetGPIORingIndicatorChanged(self, status):
        _logger.info('RockBLOCK: ring indicator = %s.', status)
        if status:
            get_messages(ack_ring=True)
