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


_logger = logging.getLogger('holonet.rockblock')


class RockBlockProtocol(object):
    def rockBlockConnected(self):
        pass

    def rockBlockDisconnected(self):
        pass

    # SIGNAL
    def rockBlockSignalUpdate(self, signal):
        pass

    def rockBlockSignalPass(self):
        pass

    def rockBlockSignalFail(self):
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

    def rockBlockTxFailed(self):
        pass

    def rockBlockTxSuccess(self, momsn):
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

        self._do_callback(RockBlockProtocol.rockBlockConnected)


    # Ensure that the connection is still alive
    def ping(self):
        self._ensureConnectionStatus()
        return self._send_and_ack_command(b'AT')


    # Handy function to check the connection is still alive, else throw an Exception
    def pingception(self):
        self._ensureConnectionStatus()

        self.s.timeout = 5
        if not self.ping():
            raise RockBlockException()

        self.s.timeout = 60


    def requestSignalStrength(self):
        self._ensureConnectionStatus()

        command = b'AT+CSQ'
        self._send_command(command)

        if self._read_next_line() == command:
            response = self._read_next_line()

            if b'+CSQ' in response:
                self._read_next_line()    # OK
                self._read_next_line()    # BLANK

                if len(response) == 6:
                    return int(response[5])

        return -1


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

        self._do_callback(RockBlockProtocol.rockBlockTxFailed)
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
            return self._read_next_line() == b'OK'
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

            if self._read_next_line() != command:
                return False

            response = self._read_next_line()
            if not response.startswith(b'+SBDIX: '):
                return False

            self.s.readline()   # BLANK
            self.s.readline()   # OK

            # +SBDIX: <MO status>, <MOMSN>, <MT status>, <MTMSN>, <MT length>,
            # <MTqueued>
            response = response[len(b'+SBDIX: '):]
            parts = response.split(b',')
            if len(parts) != 6:
                return False
            (moStatus, moMsn, mtStatus, mtMsn, mtLength, mtQueued) = \
                map(int, parts)

            # Mobile Originated
            if moStatus <= 4:
                self._clearMoBuffer()
                self._do_callback(RockBlockProtocol.rockBlockTxSuccess, moMsn)
            else:
                self._do_callback(RockBlockProtocol.rockBlockTxFailed)

            if mtStatus == 1 and mtLength > 0:
                # SBD message successfully received from the GSS.
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

        TIME_ATTEMPTS = 20
        TIME_DELAY = 1

        SIGNAL_ATTEMPTS = 10
        RESCAN_DELAY = 10
        SIGNAL_THRESHOLD = 2

        # Wait for valid Network Time
        while True:
            if TIME_ATTEMPTS == 0:
                self._do_callback(RockBlockProtocol.rockBlockSignalFail)
                return False

            if self._isNetworkTimeValid():
                break

            TIME_ATTEMPTS -= 1

            time.sleep(TIME_DELAY)


        # Wait for acceptable signal strength
        while True:
            signal = self.requestSignalStrength()

            if SIGNAL_ATTEMPTS == 0 or signal < 0:
                self._do_callback(RockBlockProtocol.rockBlockSignalFail)
                return False

            self._do_callback(RockBlockProtocol.rockBlockSignalUpdate, signal)

            if signal >= SIGNAL_THRESHOLD:
                self._do_callback(RockBlockProtocol.rockBlockSignalPass)
                return True

            SIGNAL_ATTEMPTS -= 1

            time.sleep(RESCAN_DELAY)


    def _processMtMessage(self, mtMsn):
        self._ensureConnectionStatus()

        self._send_command(b'AT+SBDRB')
        response = self._read_next_line().replace(b'AT+SBDRB\r', '').strip()

        if response == b'OK':
            _logger.warning('No message content.. strange!')
            self._do_callback(RockBlockProtocol.rockBlockRxReceived, mtMsn, b'')
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
        return self.s.readline().rstrip(b'\r')


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
