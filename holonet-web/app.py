import logging
import os

from flask import Flask, redirect, render_template, request, url_for

from holonet import mailboxes, queue_manager


app = Flask(__name__)


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
    signal = queue_manager.last_known_signal_strength
    rockblock_serial = queue_manager.rockblock_serial_identifier or "Unknown"
    rockblock_status = queue_manager.last_known_rockblock_status
    rockblock_err = queue_manager.last_txfailed_mo_status

    return render_template('index.html',
                           outbox=outbox,
                           recipients=recipients,
                           signal=signal,
                           rockblock_err=rockblock_err,
                           rockblock_serial=rockblock_serial,
                           rockblock_status=rockblock_status)


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
    queue_manager.get_messages()

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
    local_user = _get_local_user()
    messages = mailboxes.get_thread(local_user, recipient)
    return render_template('thread.html',
                           messages=messages,
                           recipient=recipient)


@app.route('/thread/<recipient>', methods=['DELETE'])
def thread_delete(recipient):
    return _thread_delete(recipient)

@app.route('/thread_delete/<recipient>')
def thread_delete_by_get(recipient):
    return _thread_delete(recipient)

def _thread_delete(recipient):
    local_user = _get_local_user()
    messages = mailboxes.delete_thread(local_user, recipient)
    return _response_return_to_previous()


def _get_local_user():
    # TODO: Some concept of signing in?
    return 'local'


def _response_return_to_previous():
    return redirect(request.referrer or url_for('index'))


if __name__ == '__main__':
    holonet_logger = logging.getLogger('holonet')
    holonet_logger.setLevel(logging.DEBUG)
    for handler in app.logger.handlers:
        holonet_logger.addHandler(handler)

    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        queue_manager.start(app.config.get('ROCKBLOCK_DEVICE'))
    app.run(debug=True, host='0.0.0.0')
