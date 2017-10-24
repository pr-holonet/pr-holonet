#    Copyright 2015 Makersnake
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import glob
import logging
import sys
import time

import serial
try:
    import RPi.GPIO as GPIO
except ImportError:
    pass


TIME_ATTEMPTS = 20
TIME_DELAY = 1
SIGNAL_ATTEMPTS = 10
RESCAN_DELAY = 10
SIGNAL_THRESHOLD = 2

GPIO_MODE = GPIO.BOARD
RING_INDICATOR_PIN = 12
RING_INDICATOR_PUD = GPIO.PUD_DOWN


_logger = logging.getLogger('holonet.rockblock')


class RockBlockProtocol(object):
    def rockBlockConnected(self):
        pass

    def rockBlockDisconnected(self):
        pass

    # SIGNAL
    def rockBlockSignalUpdate(self, signal):
        pass

    # MT
    def rockBlockRxStarted(self):
        pass

    def rockBlockRxFailed(self):
        pass

    def rockBlockRxReceived(self, mtmsn, data):
        pass

    def rockBlockRxMessageQueue(self, count):
        pass

    # MO
    def rockBlockTxStarted(self):
        pass

    def rockBlockTxFailed(self, moStatus):
        pass

    def rockBlockTxSuccess(self, momsn):
        pass

    # RING INDICATOR
    def rockBlockRingIndicatorChanged(self, status):
        pass


class RockBlockException(Exception):
    pass


class RockBlock(object):

    # May 11, 2014, at 14:23:55 (This will be 're-epoched' every couple of
    # years!)
    IRIDIUM_EPOCH = 1399818235000

    def __init__(self, portId, callback):
        self.s = None
        self.portId = portId
        self.callback = callback

        # When True, we'll automatically initiate additional sessions if more
        # messages to download.
        self.autoSession = True

        self.s = serial.Serial(self.portId, 19200, timeout=5)

        if not self._configurePort():
            self.close()
            raise RockBlockException()

        self.ping()  # KEEP SACRIFICIAL!
        self.s.timeout = 60

        if not self.ping():
            self.close()
            raise RockBlockException()

        self._do_gpio_setup()

        self._do_callback(RockBlockProtocol.rockBlockConnected)


    def _do_gpio_setup(self):
        GPIO.setmode(GPIO_MODE)
        GPIO.setup(RING_INDICATOR_PIN, GPIO.IN,
                   pull_up_down=RING_INDICATOR_PUD)
        GPIO.add_event_detect(RING_INDICATOR_PIN, GPIO.BOTH,
                              callback=self._ring_indicator_callback)

    def _ring_indicator_callback(self, _channel):
        status = bool(GPIO.input(RING_INDICATOR_PIN))
        self._do_callback(RockBlockProtocol.rockBlockRingIndicatorChanged,
                          status)


    def ping(self):
        """Ensure that the connection is still alive."""
        self._ensureConnectionStatus()
        return self._send_and_ack_command(b'AT')


    def _wait_for_network_time(self):
        retries = 0
        while True:
            if self._isNetworkTimeValid():
                return True

            retries += 1
            if retries == TIME_ATTEMPTS:
                _logger.warning('Failed to get network time after %d retries; '
                                'giving up.', retries)
                self._do_callback(RockBlockProtocol.rockBlockSignalUpdate, 0)
                return False

            _logger.debug('Failed to get network time after try %d; '
                          'will retry after %d secs.', retries, TIME_DELAY)
            time.sleep(TIME_DELAY)
        assert False  # Unreachable.


    def wait_for_good_signal(self):
        retries = 0
        while True:
            signal = self._requestSignalStrength()
            if signal >= SIGNAL_THRESHOLD:
                return True

            retries += 1
            if retries == SIGNAL_ATTEMPTS:
                _logger.warning('Failed to get good signal after %d retries; '
                                'giving up.', retries)
                return False

            _logger.debug('Failed to get good signal after try %d; '
                          'will retry after %d secs.', retries, RESCAN_DELAY)
            time.sleep(RESCAN_DELAY)
        assert False  # Unreachable.


    def _requestSignalStrength(self):
        signal = self._doRequestSignalStrength()
        _logger.debug('Signal strength is %d.', signal)
        self._do_callback(RockBlockProtocol.rockBlockSignalUpdate, signal)
        return signal


    def _doRequestSignalStrength(self):
        self._ensureConnectionStatus()

        command = b'AT+CSQ'
        self._send_command(command)
        response = self._read_next_line()

        if response != command:
            _logger.error('Incorrect echo for %s: %s', command, response)
            return -1

        response = self._read_next_line()

        if b'+CSQ' not in response or len(response) != 6:
            _logger.error('Incorrect response to %s: %s', command, response)
            return -1

        self._read_next_line()    # BLANK
        self._read_next_line()    # OK

        result = response[5] - ord('0')
        return result


    def messageCheck(self):
        self._ensureConnectionStatus()

        self._do_callback(RockBlockProtocol.rockBlockRxStarted)

        if self._attemptConnection() and self._attemptSession():
            return True

        self._do_callback(RockBlockProtocol.rockBlockRxFailed)
        return False


    def networkTime(self):
        self._ensureConnectionStatus()

        command = b'AT-MSSTM'
        self._send_command(command)

        if self._read_next_line() == command:
            response = self._read_next_line()

            self._read_next_line()   # BLANK
            self._read_next_line()   # OK

            if b'no network service' not in response:
                utc = int(response[8:], 16)
                utc = int((self.IRIDIUM_EPOCH + (utc * 90)) / 1000)
                return utc
            else:
                return 0


    def sendMessage(self, msg):
        assert isinstance(msg, bytes)

        self._ensureConnectionStatus()

        self._do_callback(RockBlockProtocol.rockBlockTxStarted)

        if self._queueMessage(msg) and self._attemptConnection():
            SESSION_DELAY = 1
            SESSION_ATTEMPTS = 3

            while True:
                SESSION_ATTEMPTS -= 1
                if SESSION_ATTEMPTS == 0:
                    break

                if self._attemptSession():
                    return True
                else:
                    time.sleep(SESSION_DELAY)

        self._do_callback(RockBlockProtocol.rockBlockTxFailed, -1)
        return False


    def getSerialIdentifier(self):
        self._ensureConnectionStatus()

        command = b'AT+GSN'
        self._send_command(command)

        if self._read_next_line() == command:
            response = self._read_next_line()
            self._read_next_line()   # BLANK
            self._read_next_line()   # OK
            return response.decode('ascii')

        return None


    # One-time initial setup function (Disables Flow Control)
    # This only needs to be called once, as is stored in non-volitile memory

    # Make sure you DISCONNECT RockBLOCK from power for a few minutes after
    # this command has been issued...
    def setup(self):
        self._ensureConnectionStatus()

        # Disable Flow Control
        if not self._send_and_ack_command(b'AT&K0'):
            return False

        # Store Configuration into Profile0
        if not self._send_and_ack_command(b'AT&W0'):
            return False

        # Use Profile0 as default
        if not self._send_and_ack_command(b'AT&Y0'):
            return False

        # Flush Memory
        if not self._send_and_ack_command(b'AT*F'):
            return False

        return True


    def close(self):
        if self.s is not None:
            self.s.close()
            self.s = None


    @staticmethod
    def listPorts():

        if sys.platform.startswith('win'):
            ports = ['COM' + str(i + 1) for i in range(256)]
        elif (sys.platform.startswith('linux') or
              sys.platform.startswith('cygwin')):
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')

        result = []

        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass

        return result


    def _queueMessage(self, msg):
        self._ensureConnectionStatus()

        msg_len = len(msg)
        if msg_len > 340:
            _logger.warning('Message is longer than 340 bytes; rejecting it.')
            return False

        msg_len_bytes = bytes(str(msg_len), 'ascii')
        command = b'AT+SBDWB=' + msg_len_bytes
        self._send_command(command)

        if (not self._read_next_line() == command or
                not self._read_next_line() == b'READY'):
            return False

        checksum = 0
        for b in msg:
            checksum += b

        self.s.write(msg)
        self.s.write(checksum.to_bytes(2, byteorder='big'))

        self._read_next_line()   # BLANK
        result = (self._read_next_line() == b'0')

        self._read_next_line()   # BLANK
        self._read_next_line()   # OK

        return result


    def _configurePort(self):
        return (self._enableEcho() and self._disableFlowControl and
                self._disableRingAlerts() and self.ping())


    def _enableEcho(self):
        self._ensureConnectionStatus()

        command = b'ATE1'
        self._send_command(command)
        response = self._read_next_line()
        if response == command or response == b'':
            response = self._read_next_line()
            if response == b'OK':
                return True
        _logger.error('Failed to enable echo; got response %s', response)
        return False


    def _disableFlowControl(self):
        self._ensureConnectionStatus()
        return self._send_and_ack_command(b'AT&K0')


    def _disableRingAlerts(self):
        self._ensureConnectionStatus()
        return self._send_and_ack_command(b'AT+SBDMTA=0')


    def _attemptSession(self):
        self._ensureConnectionStatus()

        SESSION_ATTEMPTS = 3

        while True:
            if SESSION_ATTEMPTS == 0:
                return False

            SESSION_ATTEMPTS -= 1

            command = b'AT+SBDIX'
            self._send_command(command)
            response = self._read_next_line()

            if response != command:
                _logger.error('Got bad response when creating session: %s',
                              response)
                return False

            response = self._read_next_line()
            if not response.startswith(b'+SBDIX: '):
                _logger.error('Got bad response when creating session: %s',
                              response)
                return False

            self.s.readline()   # BLANK
            self.s.readline()   # OK

            # +SBDIX: <MO status>, <MOMSN>, <MT status>, <MTMSN>, <MT length>,
            # <MTqueued>
            response = response[len(b'+SBDIX: '):]
            parts = response.split(b',')
            if len(parts) != 6:
                _logger.error('Got bad parts in response when creating '
                              'session: %s / %s.', response, parts)
                return False
            (moStatus, moMsn, mtStatus, mtMsn, mtLength, mtQueued) = \
                map(int, parts)

            # Mobile Originated
            if moStatus <= 4:
                self._clearMoBuffer()
                self._do_callback(RockBlockProtocol.rockBlockTxSuccess, moMsn)
            else:
                _logger.warning('Got moStatus %d', moStatus)
                self._do_callback(RockBlockProtocol.rockBlockTxFailed,
                                  moStatus)

            if mtStatus == 1 and mtLength > 0:
                # SBD message successfully received from the GSS.
                _logger.debug('Will process message %s', mtMsn)
                self._processMtMessage(mtMsn)

            # AUTOGET NEXT MESSAGE

            self._do_callback(RockBlockProtocol.rockBlockRxMessageQueue,
                              mtQueued)

            # There are additional MT messages to queued to download
            if mtQueued > 0 and self.autoSession:
                self._attemptSession()

            if moStatus <= 4:
                return True

        assert False  # Unreachable, while (True) above.


    def _attemptConnection(self):
        self._ensureConnectionStatus()
        return self._wait_for_network_time() and self.wait_for_good_signal()


    def _processMtMessage(self, mtMsn):
        self._ensureConnectionStatus()

        self._send_command(b'AT+SBDRB')
        response = self._read_next_line().replace(b'AT+SBDRB\r', '').strip()

        if response == b'OK':
            _logger.warning('No message content.. strange!')
            self._do_callback(RockBlockProtocol.rockBlockRxReceived,
                              mtMsn, b'')
        else:
            content = response[2:-2]
            self._do_callback(RockBlockProtocol.rockBlockRxReceived, mtMsn,
                              content)
            self.s.readline()   # BLANK?


    def _isNetworkTimeValid(self):
        self._ensureConnectionStatus()

        command = b'AT-MSSTM'
        self._send_command(command)

        if self._read_next_line() != command:  # Echo
            return False

        response = self._read_next_line()
        if response.startswith(b'-MSSTM'):
            # -MSSTM: a5cb42ad / no network service
            self.s.readline()   # OK
            self.s.readline()   # BLANK

            if len(response) == 16:
                return True

        return False


    def _clearMoBuffer(self):
        self._ensureConnectionStatus()

        command = b'AT+SBDD0'
        self._send_command(command)

        if self._read_next_line() != command:
            return False

        if self._read_next_line() != b'0':
            return False

        self.s.readline()  # BLANK
        if self._read_next_line() != b'OK':
            return False

        return True


    def _send_and_ack_command(self, cmd):
        self._send_command(cmd)
        return self._read_ack(cmd)


    def _ensureConnectionStatus(self):
        if self.s is None or not self.s.isOpen():
            raise RockBlockException()


    def _send_command(self, cmd):
        self.s.write(cmd + b'\r')


    def _read_next_line(self):
        """Read the next line, and return it with the trailing newline
           stripped."""
        return self.s.readline().rstrip()


    def _read_ack(self, cmd):
        """Read the next two lines, checking that the first is the given cmd
           echoed back, and the next is b'OK'."""
        return (self._read_next_line() == cmd and
                self._read_next_line() == b'OK')


    def _do_callback(self, f, *args):
        cb = getattr(self.callback, f.__name__, None)
        if cb is None:
            return
        cb(*args)
