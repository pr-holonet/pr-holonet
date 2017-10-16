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

import collections
import glob
import sys
import time

import serial


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

        try:
            self.s = serial.Serial(self.portId, 19200, timeout=5)

            if self._configurePort():

                self.ping()  # KEEP SACRIFICIAL!

                self.s.timeout = 60

                if self.ping():
                    if (self.callback is not None and
                            isinstance(self.callback.rockBlockConnected,
                                       collections.Callable)):
                        self.callback.rockBlockConnected()
                        return

            self.close()
            # raise RockBlockException()

        except Exception:
            print("__init__ failed!")
            raise RockBlockException()


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

        command = "AT+CSQ"
        self._send_command(command)

        if self._read_next_line().decode() == command:
            response = self._read_next_line().decode()

            if response.find("+CSQ") >= 0:
                self._read_next_line()    # OK
                self._read_next_line()    # BLANK

                if len(response) == 6:
                    return int(response[5])

        return -1


    def messageCheck(self):
        self._ensureConnectionStatus()

        if (self.callback is not None and
                isinstance(self.callback.rockBlockRxStarted,
                           collections.Callable)):
            self.callback.rockBlockRxStarted()

        if self._attemptConnection() and self._attemptSession():
            return True
        else:
            if (self.callback is not None and
                    isinstance(self.callback.rockBlockRxFailed,
                               collections.Callable)):
                self.callback.rockBlockRxFailed()


    def networkTime(self):
        self._ensureConnectionStatus()

        command = "AT-MSSTM"
        self._send_command(command)

        if self._read_next_line().decode() == command:
            response = self._read_next_line().decode()

            self._read_next_line()   # BLANK
            self._read_next_line()   # OK

            if "no network service" not in response:
                utc = int(response[8:], 16)
                utc = int((self.IRIDIUM_EPOCH + (utc * 90)) / 1000)
                return utc
            else:
                return 0


    def sendMessage(self, msg):
        self._ensureConnectionStatus()

        if (self.callback is not None and
                isinstance(self.callback.rockBlockTxStarted,
                           collections.Callable)):
            self.callback.rockBlockTxStarted()

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

        if (self.callback is not None and
                isinstance(self.callback.rockBlockTxFailed,
                           collections.Callable)):
            self.callback.rockBlockTxFailed()

        return False


    def getSerialIdentifier(self):
        self._ensureConnectionStatus()

        command = "AT+GSN"
        self._send_command(command)

        if self._read_next_line().decode() == command:
            response = self._read_next_line().decode()

            self._read_next_line()   # BLANK
            self._read_next_line()   # OK

            return response


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


    # functions for use with the HOLONET API
    # send_message(recipient, body) with some kind of error / success response
    # is_message_waiting() -> bool
    # get_messages() -> string list
    # get_signal_strength() -> int```

    # Need to refactor this later but here goes...

    def send_message(self, recipient, body):
        # this method sends a message to the rock block module
        # for now only merges the recipient with the body and uses the old send message function
        new_msg = recipient + ":" + body
        self.sendMessage(new_msg)

    def is_message_waiting(self):
        self.messageCheck()

    def get_messages(self):
        pass

    def get_signal_strength(self):
        response = self.requestSignalStrength()
        return response


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

        if len(msg) > 340:
            print("sendMessageWithBytes bytes should be <= 340 bytes")
            return False

        command = "AT+SBDWB=" + str(len(msg))
        self._send_command(command)

        if self._read_next_line().decode() == command:
            if self._read_next_line().decode() == "READY":
                checksum = 0

                for c in msg:
                    checksum = checksum + ord(c)

                self.s.write(str(msg).encode())

                self.s.write(bytes(chr(checksum >> 8), 'ascii'))
                self.s.write(bytes(chr(checksum & 0xFF), 'ascii'))

                self._read_next_line()   # BLANK

                result = False

                if self._read_next_line() == b"0":
                    result = True

                self._read_next_line()   # BLANK
                self._read_next_line()   # OK

                return result

        return False


    def _configurePort(self):
        return (self._enableEcho() and self._disableFlowControl and
                self._disableRingAlerts() and self.ping())


    def _enableEcho(self):
        self._ensureConnectionStatus()

        command = "ATE1"
        self._send_command(command)

        response = self._read_next_line().decode()

        if response == command or response == "":
            if self._read_next_line().decode() == "OK":
                return True

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

            command = "AT+SBDIX"
            self._send_command(command)

            if self._read_next_line().decode() == command:

                response = self._read_next_line().decode()

                if response.find("+SBDIX:") >= 0:
                    self.s.readline()   # BLANK
                    self.s.readline()   # OK

                    # +SBDIX:<MO status>,<MOMSN>,<MT status>,<MTMSN>,
                    # <MT length>,<MTqueued>
                    response = response.replace("+SBDIX: ", "")
                    parts = response.split(",")
                    moStatus = int(parts[0])
                    moMsn = int(parts[1])
                    mtStatus = int(parts[2])
                    mtMsn = int(parts[3])
                    mtLength = int(parts[4])
                    mtQueued = int(parts[5])

                    # Mobile Originated
                    if moStatus <= 4:
                        self._clearMoBuffer()

                        if (self.callback is not None and
                                isinstance(self.callback.rockBlockTxSuccess,
                                           collections.Callable)):
                            self.callback.rockBlockTxSuccess(moMsn)
                    else:
                        if (self.callback is not None and
                                isinstance(self.callback.rockBlockTxFailed,
                                           collections.Callable)):
                            self.callback.rockBlockTxFailed()

                    if mtStatus == 1 and mtLength > 0:
                        # SBD message successfully received from the GSS.
                        self._processMtMessage(mtMsn)

                    # AUTOGET NEXT MESSAGE

                    if (self.callback is not None and
                            isinstance(self.callback.rockBlockRxMessageQueue,
                                       collections.Callable)):
                        self.callback.rockBlockRxMessageQueue(mtQueued)

                    # There are additional MT messages to queued to download
                    if mtQueued > 0 and self.autoSession:
                        self._attemptSession()

                    if moStatus <= 4:
                        return True

        return False


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
                if (self.callback is not None and
                        isinstance(self.callback.rockBlockSignalFail,
                                   collections.Callable)):
                    self.callback.rockBlockSignalFail()
                return False

            if self._isNetworkTimeValid():
                break

            TIME_ATTEMPTS -= 1

            time.sleep(TIME_DELAY)


        # Wait for acceptable signal strength
        while True:
            signal = self.requestSignalStrength()

            if SIGNAL_ATTEMPTS == 0 or signal < 0:
                print("NO SIGNAL")

                if (self.callback is not None and
                        isinstance(self.callback.rockBlockSignalFail,
                                   collections.Callable)):
                    self.callback.rockBlockSignalFail()
                return False

            self.callback.rockBlockSignalUpdate(signal)

            if signal >= SIGNAL_THRESHOLD:
                if (self.callback is not None and
                        isinstance(self.callback.rockBlockSignalPass,
                                   collections.Callable)):
                    self.callback.rockBlockSignalPass()
                return True

            SIGNAL_ATTEMPTS -= 1

            time.sleep(RESCAN_DELAY)


    def _processMtMessage(self, mtMsn):
        self._ensureConnectionStatus()

        self._send_command("AT+SBDRB")

        response = self._read_next_line().decode('ascii').replace("AT+SBDRB\r", "").strip()

        if response == "OK":
            print("No message content.. strange!")

            if (self.callback is not None and
                    isinstance(self.callback.rockBlockRxReceived,
                               collections.Callable)):
                self.callback.rockBlockRxReceived(mtMsn, "")
        else:
            content = response[2:-2]

            if (self.callback is not None and
                    isinstance(self.callback.rockBlockRxReceived,
                               collections.Callable)):
                self.callback.rockBlockRxReceived(mtMsn, content)

            self.s.readline()   # BLANK?


    def _isNetworkTimeValid(self):
        self._ensureConnectionStatus()

        command = "AT-MSSTM"
        self._send_command(command)

        if self._read_next_line().decode() == command:  # Echo
            response = self._read_next_line().decode()

            if response.startswith("-MSSTM"):    # -MSSTM: a5cb42ad / no network service
                self.s.readline()   # OK
                self.s.readline()   # BLANK

                if len(response) == 16:
                    return True

        return False


    def _clearMoBuffer(self):
        self._ensureConnectionStatus()

        command = "AT+SBDD0"
        self._send_command(command)

        if self._read_next_line().decode() == command:
            if self._read_next_line().decode() == "0":
                self.s.readline()  # BLANK
                if self._read_next_line().decode() == "OK":
                    return True

        return False


    def _send_and_ack_command(self, cmd):
        self._send_command(cmd)
        return self._read_ack(cmd)


    def _ensureConnectionStatus(self):
        if self.s is None or not self.s.isOpen():
            raise RockBlockException()


    def _send_command(self, cmd):
        if isinstance(cmd, str):
            cmd = cmd.encode('ascii')
        self.s.write(cmd + b'\r')


    def _read_next_line(self):
        """Read the next line, and return it with the trailing newline
           stripped."""
        return self.s.readline().rstrip(b'\n')


    def _read_ack(self, cmd):
        """Read the next two lines, checking that the first is the given cmd
           echoed back, and the next is b'OK'."""
        return (self._read_next_line() == cmd and
                self._read_next_line() == b'OK')
