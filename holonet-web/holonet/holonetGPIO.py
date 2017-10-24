import logging

try:
    import RPi.GPIO as GPIO
except ImportError:
    from . import mockGPIO as GPIO

from .utils import do_callback


GPIO_MODE = GPIO.BOARD
RING_INDICATOR_PIN = 12
RING_INDICATOR_PUD = GPIO.PUD_DOWN

_logger = logging.getLogger('holonet.holonetGPIO')


class HolonetGPIOProtocol(object):  # pylint: disable=too-few-public-methods
    def holonetGPIORingIndicatorChanged(self, status):
        pass


class HolonetGPIO(object):  # pylint: disable=too-few-public-methods
    def __init__(self, callback):
        self.callback = callback

        GPIO.setmode(GPIO_MODE)
        GPIO.setup(RING_INDICATOR_PIN, GPIO.IN,
                   pull_up_down=RING_INDICATOR_PUD)
        GPIO.add_event_detect(RING_INDICATOR_PIN, GPIO.BOTH,
                              callback=self._ring_indicator_callback)

    def _ring_indicator_callback(self, _channel):
        status = bool(GPIO.input(RING_INDICATOR_PIN))
        self._do_callback(HolonetGPIOProtocol.holonetGPIORingIndicatorChanged,
                          status)

    def _do_callback(self, f, *args):
        do_callback(self.callback, f, *args)
