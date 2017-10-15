from flask import Flask, redirect, render_template, request, url_for

from holonet import mailboxes, queue_manager


app = Flask(__name__)


@app.route('/')
def index():
    outbox = mailboxes.read_outbox()
    local_user = _get_local_user()
    recipients = mailboxes.list_recipients(local_user)

    return render_template('index.html',
                           outbox=outbox,
                           recipients=recipients)


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
    for msg in messages:
        msg['arrow'] = ('&larr;' if msg['direction'] == 'in' else '&rarr;')
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
    queue_manager.start()
    app.run(debug=True, host='0.0.0.0')
