import logging
from logging.handlers import RotatingFileHandler
import os

from flask import Flask, redirect, render_template, request, url_for

from holonet import mailboxes, queue_manager
from holonet.utils import printable_phone_number


LOG_FILE = '/var/opt/pr-holonet/log/holonet-web.log'
HOLONET_LOG_LEVEL = logging.DEBUG


is_flask_subprocess = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")

app = Flask(__name__)

holonet_logger = logging.getLogger('holonet')
holonet_logger.setLevel(HOLONET_LOG_LEVEL)
for handler in app.logger.handlers:
    holonet_logger.addHandler(handler)

if is_gunicorn:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1000000, backupCount=1)
    fmt = '%(asctime)-15s %(levelname)-7.7s %(message)s'
    handler.setFormatter(logging.Formatter(fmt=fmt))
    holonet_logger.addHandler(handler)
    app.logger.addHandler(handler)

if not is_gunicorn:
    mailboxes.mailboxes_root = \
        os.path.abspath(os.path.join(thisdir, '..', 'mailboxes'))

if is_flask_subprocess or is_gunicorn:
    queue_manager.start(app.config.get('ROCKBLOCK_DEVICE'))


@app.route('/')
def index():
    # Note that this is an async request to refresh the signal strength.  If
    # it does't get done by the time we've parsed the mailboxes (which is
    # likely because we should be reading the SD card a lot faster than the
    # serial line) then we'll be reporting the stale strength, not the new one.
    # That's OK for now.
    queue_manager.request_signal_strength()

    outbox = mailboxes.read_outbox()
    local_user = _get_local_user()
    recipients = mailboxes.list_recipients(local_user)
    recipients_printable = _printable_phone_number_dict(recipients)
    pending = queue_manager.message_pending_senders.keys()
    pending_printable = _printable_phone_number_dict(pending)
    signal = queue_manager.last_known_signal_strength
    rockblock_serial = queue_manager.rockblock_serial_identifier or "Unknown"
    rockblock_status = queue_manager.last_known_rockblock_status
    rockblock_err = queue_manager.last_txfailed_mo_status

    return render_template('index.html',
                           outbox=outbox,
                           pending=pending,
                           pending_printable=pending_printable,
                           recipients=recipients,
                           recipients_printable=recipients_printable,
                           signal=signal,
                           rockblock_err=rockblock_err,
                           rockblock_serial=rockblock_serial,
                           rockblock_status=rockblock_status)


def _printable_phone_number_dict(nos):
    return dict(map(lambda x: (x, printable_phone_number(x)), nos))


@app.route('/send_message', methods=['POST'])
def send_message():
    body = request.form.get('body')
    recipient = request.form.get('recipient')

    resp = _response_return_to_previous()

    if not body or not recipient:
        return resp

    local_user = _get_local_user()

    mailboxes.queue_message_send(local_user, recipient, body)
    queue_manager.check_outbox()

    return resp


@app.route('/send_receive', methods=['POST'])
def send_receive():
    queue_manager.check_outbox()
    queue_manager.get_messages(ack_ring=False)

    return _response_return_to_previous()


@app.route('/test')
def test():
    inbox = mailboxes.read_inbox()
    outbox = mailboxes.read_outbox()
    local_user = _get_local_user()
    recipients = mailboxes.list_recipients(local_user)

    return render_template('test.html',
                           inbox=inbox,
                           outbox=outbox,
                           recipients=recipients)


@app.route('/thread/<recipient>')
def thread(recipient):
    queue_manager.clear_message_pending(recipient)
    local_user = _get_local_user()
    messages = mailboxes.get_thread(local_user, recipient)
    recipient_printable = printable_phone_number(recipient)
    return render_template('thread.html',
                           messages=messages,
                           recipient=recipient,
                           recipient_printable=recipient_printable)


@app.route('/thread/<recipient>', methods=['DELETE'])
def thread_delete(recipient):
    return _thread_delete(recipient)

@app.route('/thread_delete/<recipient>')
def thread_delete_by_get(recipient):
    return _thread_delete(recipient)

def _thread_delete(recipient):
    queue_manager.clear_message_pending(recipient)
    local_user = _get_local_user()
    messages = mailboxes.delete_thread(local_user, recipient)
    return _response_return_to_previous()


def _get_local_user():
    # TODO: Some concept of signing in?
    return 'local'


def _response_return_to_previous():
    return redirect(request.referrer or url_for('index'))


if __name__ == '__main__':
    app.jinja_env.auto_reload = True
    app.run(debug=True, host='0.0.0.0')
