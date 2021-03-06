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
#
'''
All changes made

Copyright 2017 Ewan Mellor, Rolf Widenfelt

Changes authored by Hadi Esiely:
Copyright 2018 The Johns Hopkins University Applied Physics Laboratory LLC.
'''



import glob
import logging
import sys
import time
import traceback
import serial

from .utils import do_callback


TIME_ATTEMPTS = 20
TIME_DELAY = 1
SIGNAL_ATTEMPTS = 10
# used for waiting on rockblock to send all data to system
RESCAN_DELAY = 10
SIGNAL_THRESHOLD = 2
SYNC_COMMS_ATTEMPTS = 3
ROCKBLOCK_POWER_BACKOFF = 40

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
            signal = self.requestSignalStrength()
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

    def requestSignalStrength(self):
        signal = self._doRequestSignalStrength()
        _logger.debug('Signal strength is %d.', signal)
        self._do_callback(RockBlockProtocol.rockBlockSignalUpdate, signal)
        return signal

    def _doRequestSignalStrength(self):
        self._ensureConnectionStatus()

        command = b'AT+CSQ'
        if not self._send_command_and_read_echo(command):
            return -1

        response = self._read_next_line()
        if b'+CSQ' not in response or len(response) != 6:
            _logger.error('Incorrect response to %s: %s', command, response)
            return -1

        if not self._read_ok(command):
            return -1

        result = response[5] - ord('0')
        return result

    def messageCheck(self, ack_ring):
        """
        Args:
            ack_ring (bool): Whether this call is acking a ring indicator
                from the network.  If it is, we need to use the +SBDIXA command
                rather than +SBDIX.
        """
        self._ensureConnectionStatus()

        self._do_callback(RockBlockProtocol.rockBlockRxStarted)

        if self._attemptConnection() and \
                self._attemptSession(ack_ring=ack_ring):
            return True

        self._do_callback(RockBlockProtocol.rockBlockRxFailed)
        return False

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
        if not self._send_command_and_read_echo(command):
            return None

        response = self._read_next_line()
        if not self._read_ok(command):
            return None
        return response.decode('ascii')

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

        if (self._read_next_line() != command or
                self._read_next_line() != b'READY'):
            return False

        checksum = 0
        for b in msg:
            checksum += b

        # _logger.debug('RockBLOCK: queuing message: %s', msg)
        self.s.write(msg)
        self.s.write(checksum.to_bytes(2, byteorder='big'))

        result = (self._read_next_line() == b'0')
        if not self._read_ok(command):
            return False
        return result

    def _configurePort(self):
        return (self._enableEcho() and self._disableFlowControl and
                self._enableRingAlerts() and self.ping())

    def _enableEcho(self):
        self._ensureConnectionStatus()

        command = b'ATE1'
        self._send_command(command)
        response = self._read_next_line()
        if response == command or response == b'':
            return self._read_ok(command)
        else:
            _logger.error('Failed to enable echo; got response %s', response)
            return False

    def _disableFlowControl(self):
        self._ensureConnectionStatus()
        return self._send_and_ack_command(b'AT&K0')

    def _enableRingAlerts(self):
        self._ensureConnectionStatus()
        return self._send_and_ack_command(b'AT+SBDMTA=1')

    def _attemptSession(self, ack_ring=False):
        self._ensureConnectionStatus()

        SESSION_ATTEMPTS = 3

        while True:
            if SESSION_ATTEMPTS == 0:
                return False

            SESSION_ATTEMPTS -= 1

            command = b'AT+SBDIXA' if ack_ring else b'AT+SBDIX'
            if not self._send_command_and_read_echo(command):
                _logger.warning("Warning: Comms with rockblock out of sync while trying to transmit %s. Attempting "
                                "ping after 10 second sleep", command)
                time.sleep(RESCAN_DELAY)
                # flush input buffer for any random data received
                self.s.reset_input_buffer()
                # Echo or read fail. Try to sync comms again and send the command, otherwise fail
                system_synced = False
                for x in range(1, SYNC_COMMS_ATTEMPTS):
                    system_synced = self.ping()
                if not system_synced:
                    _logger.error("Sync Failed")
                    return False
                else:
                    _logger.info("Sync Successful")
                    self._send_command_and_read_echo(command)

            response = self._read_next_line()
            if not response.startswith(b'+SBDIX: '):
                _logger.error('Got bad response when creating session: %s',
                              response)
                return False

            if not self._read_ok(command):
                return False

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
                _logger.debug('Will process message %s. %s additional messages queued', mtMsn, mtQueued)
                self._processMtMessage(mtMsn)

            # AUTOGET NEXT MESSAGE

            self._do_callback(RockBlockProtocol.rockBlockRxMessageQueue,
                              mtQueued)

            # There are additional MT messages to queued to download
            if mtQueued > 0 and self.autoSession:
                _logger.debug("Getting signal strength before retrieving remaining %s messages", str(mtQueued))
                if self.wait_for_good_signal():
                    _logger.debug(" %s messages queued. Retrieving the next one", str(mtQueued))
                    self._attemptSession()
                else:
                    _logger.warning("Failed to get good signal. Aborting message retrieval. %s messages queued",
                                    mtQueued)

            if moStatus <= 4:
                return True

        assert False  # Unreachable, while (True) above.

    def _attemptConnection(self):
        self._ensureConnectionStatus()
        return self._wait_for_network_time() and self.wait_for_good_signal()

    def _processMtMessage(self, mtMsn):
        RESP_CHECKSUM_SIZE = 2
        RESP_MSG_LEN_SIZE = 2

        self._ensureConnectionStatus()

        command = b'AT+SBDRB'
        self._send_command(command)
        # wait some time to ensure we get the checksum as well
        response = self._read_next_line()
        if not response.startswith(command + b'\r'):
            _logger.error('Incorrect echo for %s: %s', command, response)
            return
        _logger.debug('Received message from rockblock: "%s"', response)
        # discard command echo and RC
        response = response[(len(command) + 1):]

        if response == b'OK':
            _logger.warning('No message content.. strange!')
        else:
            # TODO: Fix checksum, it is broken.
            # TODO: rewrite the process for getting the data so that bytes are counted as reported by the rockblock
            reported_msg_len = int.from_bytes(response[:2], byteorder='big')
            # discard message length (2 bytes)
            rcvd_msg = response[RESP_MSG_LEN_SIZE:]
            rcvd_msg_len = len(rcvd_msg)

            if rcvd_msg_len < reported_msg_len + RESP_CHECKSUM_SIZE:
                _logger.warning("Incomplete message received. Waiting for completion. Holding off for %s s",
                                str(TIME_DELAY))
                time.sleep(TIME_DELAY)
                response += self._read_next_line()
                _logger.debug("Updated message from rockblock is: \n%s", response)
                rcvd_msg = response[RESP_MSG_LEN_SIZE:RESP_MSG_LEN_SIZE + reported_msg_len]
                rcvd_msg_len = len(rcvd_msg)
                _logger.debug("Captured received message:\n%s", rcvd_msg)

            if rcvd_msg_len < reported_msg_len + RESP_CHECKSUM_SIZE:
                _logger.warning(
                    'Ignoring message length mismatch! %s counted != %s reported in message %s (parsed as: "%s")',
                    rcvd_msg_len, reported_msg_len, response, rcvd_msg)

            our_checksum = sum(map(int, rcvd_msg[:-RESP_CHECKSUM_SIZE])) & 0xffff
            # Read one more line in case the checksum was in late.
            # TODO: Handle delayed responses better
            checksum_read = response[RESP_MSG_LEN_SIZE + reported_msg_len: RESP_MSG_LEN_SIZE + reported_msg_len + 2]
            checksum_read = int.from_bytes(checksum_read, byteorder='big')

            if our_checksum != checksum_read:
                _logger.warning('Ignoring checksum failure! %s (our calculated checksum) != %s (reported '
                                'checksum)  in message %s', our_checksum, checksum_read, response)

            if response[:-RESP_CHECKSUM_SIZE] != b'OK':
                if not self._read_ok(command):
                    return False
        rcvd_msg = rcvd_msg[:-RESP_CHECKSUM_SIZE]
        self._do_callback(RockBlockProtocol.rockBlockRxReceived, mtMsn, rcvd_msg)

    def _isNetworkTimeValid(self):
        self._ensureConnectionStatus()

        command = b'AT-MSSTM'
        if not self._send_command_and_read_echo(command):
            # TODO: I probably need to just create a resync_comms method instead of pasting this all over the place
            _logger.warning("Warning: Comms with rockblock out of sync while trying to transmit %s. Attempting ping "
                            "after 10 second sleep", command)
            time.sleep(RESCAN_DELAY)
            # flush input buffer for any random data received
            self.s.reset_input_buffer()
            # Echo or read fail. Try to sync comms again and send the command, otherwise fail
            system_synced = False
            for x in range(1, SYNC_COMMS_ATTEMPTS):
                system_synced = self.ping()
            if not system_synced:
                _logger.error("Sync Failed")
                return False
            else:
                _logger.info("Sync Successful")
                self._send_command_and_read_echo(command)

        response = self._read_next_line()
        if response.startswith(b'-MSSTM'):
            # -MSSTM: a5cb42ad / no network service
            if not self._read_ok(command):
                return False

            if len(response) == 16:
                return True

        return False

    def _clearMoBuffer(self):
        self._ensureConnectionStatus()

        command = b'AT+SBDD0'
        if not self._send_command_and_read_echo(command):
            return False
        if self._read_next_line() != b'0':
            return False
        return self._read_ok(command)

    def _send_and_ack_command(self, cmd):
        self._send_command(cmd)
        return self._read_ack(cmd)

    def _send_command_and_read_echo(self, cmd):
        self._send_command(cmd)
        return self._read_echo(cmd)

    def _ensureConnectionStatus(self):
        if self.s is None or not self.s.isOpen():
            raise RockBlockException()

    def _send_command(self, cmd):
        # _logger.debug('RockBLOCK: sending cmd: %s', cmd)
        self.s.write(cmd + b'\r')

    def _read_next_line(self):
        """Read the next line, and return it with the trailing newline
           stripped."""

        next_line = None
        try:
            next_line = self.s.readline().rstrip()
        except serial.SerialException as e_thrown:
            # SerialExceptions tend to occur on the RaspberryPi depending on how it is powered. Backoff for 40 seconds
            _logger.warning("SerialException detected. Check power and data cabling on your system. \n" + str(e_thrown))
            _logger.warning("\nTraceback:\n" )
            traceback.print_last()
            # backoff of the Rockblock comms once and try SYNC_COMMS_ATTEMPTS times. Else, quit.
            time.sleep(ROCKBLOCK_POWER_BACKOFF)

            # TODO: build a better design that does not require backing off so much
            break_now = False
            for x in range(0,SYNC_COMMS_ATTEMPTS):
                try:
                    next_line = self.s.readline().rstrip()
                except serial.SerialException:
                    _logger.warning("SerialException recovery failed. Attempt " + str(x) + " of " + str(
                        SYNC_COMMS_ATTEMPTS))
                    time.sleep(ROCKBLOCK_POWER_BACKOFF)
                    if x == SYNC_COMMS_ATTEMPTS:
                        break
                else:
                    break

        finally:
            # _logger.debug('RockBLOCK: read line %s', result)
            # TODO: Need to properly tokenize return strings and make sure they are being properly inspected
            # TODO: Tokenize string and eval number of words in it. if more than expected comms out of sync
            if next_line is None:
                _logger.debug("No data read from serial. Trying again")
                self._read_next_line()
            elif next_line.strip(b'\r') == b'SBDRING' or next_line == b'':
                # Unsolicited ring notification.  Ignore it, we're using the GPIO
                # pin so we already know.
                # Or a blank line.  Ignore them because we're either getting
                # spurious ones or you get one before the SBDRING (not sure which).
                _logger.debug("Ignoring received data. Trying again. \nReceived:\n %s\n", str(next_line))
                return self._read_next_line()
            else:
                result = next_line
                return result

    def _read_ack(self, cmd):
        """Read the next two lines, checking that the first is the given cmd
           echoed back, and the next is b'OK'."""
        return (self._read_echo(cmd) and
                self._read_ok(cmd))

    def _read_echo(self, cmd):
        """Read the next line, checking that it matches the given cmd."""
        response = self._read_next_line()
        result = response == cmd
        if not result:
            _logger.error('Incorrect echo for %s: %s', cmd, response)
        return result

    def _read_ok(self, cmd):
        """Read the next line, checking that it is b'OK'."""
        response = self._read_next_line()
        result = response == b'OK'
        if not result:
            _logger.error('Got %s when expecting OK in response to %s',
                          response, cmd)
        return result

    def _do_callback(self, f, *args):
        do_callback(self.callback, f, *args)
