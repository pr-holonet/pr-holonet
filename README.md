# pr-holonet

| Pi pin # | Pi pin desc        | RockBLOCK pin # | RockBLOCK pin desc  |
|----------|--------------------|-----------------|---------------------|
| 2        | 5V power           | 8               | 5v In               |
| 6        | Ground             | 7               | Ground              |
| 8        | TXD0 (GPIO 14)     | 2               | RXC                 |
| 10       | RXDO (GPIO 15)     | 3               | TXD                 |
| 12       | GPIO 18 (PCM\_CLK) | 10              | RI (Ring Indicator) |
| 14       | Ground             | 6               | Ground              |

## holonet-web

This is the web service that runs on the Raspberry Pi.  The end user
connects to this to send and receive messages.

It requires Python 3, Flask, and the RPi.GPIO module.  In production
deployments we use Gunicorn and supervisord.

### Installation instructions

In production, files are placed in `/opt/pr-holonet/holonet-web`, with
log files and mailboxes placed in `/var/opt/pr-holonet`.

```
# As root:
apt-get install python3 python3-flask gunicorn3 python3-rpi.gpio supervisor

mkdir -p /opt/pr-holonet
mkdir -p /var/opt/pr-holonet/log

# Place the holonet-web source code in /opt/pr-holonet/holonet-web.

ln -s /opt/pr-holonet/holonet-web/pr-holonet-web.conf /etc/supervisor/conf.d/
service supervisor reload
```

### Developer installation instructions

You can run the app using the Flask debug server.  If you don't have
a RockBLOCK attached and aren't running on a Raspberry Pi, then those
parts will just disable themselves.

We use pycodestyle, pylint, pytest, and setuptools.

```
# Create and activate a virtualenv if you want.
pip3 install --user flask pycodestyle pylint pytest RPi.GPIO setuptools

cd pr-holonet/holonet-web

pycodestyle
python3 setup.py lint
python3 setup.py test

python3 app.py
```
