import atexit
import logging

try:
    import RPi.GPIO as GPIO
except ImportError:
    from . import mockGPIO as GPIO

from .utils import do_callback


_GPIO_MODE = GPIO.BOARD
_CONNECTION_STATUS_RED_PIN = 22
_CONNECTION_STATUS_GREEN_PIN = 24
_CONNECTION_STATUS_BLUE_PIN = 26
_MESSAGE_PENDING_PIN = 16
_RING_INDICATOR_PIN = 12
_RING_INDICATOR_PUD = GPIO.PUD_DOWN

RED = 1
YELLOW = 2
GREEN = 3
BLUE = 4


_logger = logging.getLogger('holonet.holonetGPIO')


class HolonetGPIOProtocol(object):  # pylint: disable=too-few-public-methods
    def holonetGPIORingIndicatorChanged(self, status):
        pass


class HolonetGPIO(object):
    def __init__(self, callback):
        self.callback = callback

        atexit.register(_cleanup)

        GPIO.setmode(_GPIO_MODE)
        GPIO.setup(_RING_INDICATOR_PIN, GPIO.IN,
                   pull_up_down=_RING_INDICATOR_PUD)
        GPIO.setup(_CONNECTION_STATUS_RED_PIN, GPIO.OUT)
        GPIO.setup(_CONNECTION_STATUS_GREEN_PIN, GPIO.OUT)
        GPIO.setup(_CONNECTION_STATUS_BLUE_PIN, GPIO.OUT)
        GPIO.setup(_MESSAGE_PENDING_PIN, GPIO.OUT)
        GPIO.add_event_detect(_RING_INDICATOR_PIN, GPIO.BOTH,
                              callback=self._ring_indicator_callback)


    @staticmethod
    def set_led_connection_status(status):
        _logger.debug('Connection status LED: %s', status)

        r = _boolToGPIO(status == RED or status == YELLOW)
        g = _boolToGPIO(status == YELLOW or status == GREEN)
        b = _boolToGPIO(status == BLUE)
        GPIO.output(_CONNECTION_STATUS_RED_PIN, r)
        GPIO.output(_CONNECTION_STATUS_GREEN_PIN, g)
        GPIO.output(_CONNECTION_STATUS_BLUE_PIN, b)

    @staticmethod
    def set_led_message_pending(status):
        _logger.debug('Message pending LED: %s', status)

        val = _boolToGPIO(status)
        GPIO.output(_MESSAGE_PENDING_PIN, val)


    def _ring_indicator_callback(self, _channel):
        status = bool(GPIO.input(_RING_INDICATOR_PIN))
        self._do_callback(HolonetGPIOProtocol.holonetGPIORingIndicatorChanged,
                          status)

    def _do_callback(self, f, *args):
        do_callback(self.callback, f, *args)


def _boolToGPIO(v):
    return GPIO.HIGH if v else GPIO.LOW


def _cleanup():
    GPIO.cleanup()
