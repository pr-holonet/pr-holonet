BOARD = 1
BOTH = 1
IN = 1
OUT = 2
HIGH = 1
LOW = 0
PUD_DOWN = 1


def setmode(_mode):
    pass

def setup(_channel, _mode, pull_up_down=None):
    _ = pull_up_down

def add_event_detect(_channel, _mode, callback):
    _ = callback

def input(_channel):  # pylint: disable=redefined-builtin
    return 0

def output(_channel, _val):
    pass

def cleanup():
    pass
