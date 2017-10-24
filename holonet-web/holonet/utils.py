from datetime import datetime
import errno
import os


def do_callback(handler, f, *args):
    cb = getattr(handler, f.__name__, None)
    if cb is None:
        return None
    return cb(*args)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as err:
        if err.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def utcnow_str():
    return datetime.utcnow().isoformat('T')


def timestamp_filename(ts, ext):
    return '%s.%s' % (ts.replace(':', '.'), ext)
