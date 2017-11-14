# pr-holonet

| Pi pin # | Pi pin desc        | RockBLOCK pin # | RockBLOCK pin desc  |
|----------|--------------------|-----------------|---------------------|
| 2        | 5V power           | 8               | 5v In               |
| 6        | Ground             | 7               | Ground              |
| 8        | TXD0 (GPIO 14)     | 2               | RXC                 |
| 10       | RXDO (GPIO 15)     | 3               | TXD                 |
| 12       | GPIO 18 (PCM\_CLK) | 10              | RI (Ring Indicator) |
| 14       | Ground             | 6               | Ground              |

LED pinouts follow.  This table, and the code, assume that the connection
status LED is an RGB LED with common cathode, and the message pending LED
is a simple one-color LED.  Obviously if you package the LEDs somehow then
you can run a common ground and won't need to use all the ground pins.

Each LED anode will need a current-limiting resistor in series, sized to
suit the RPi's GPIO limits (17 mA limit at 3.3V is recommended).

| Pi pin # | Pi pin desc        | Connection                             |
|----------|--------------------|----------------------------------------|
| 16       | GPIO 23            | Message pending LED anode              |
| 20       | Ground             | Message pending LED cathode            |
| 22       | GPIO 25            | Connection status LED red anode        |
| 24       | GPIO 8             | Connection status LED green anode      |
| 26       | GPIO 7             | Connection status LED blue anode       |
| 25       | Ground             | Connection status LED cathode          |


## holonet-web

This is the web service that runs on the Raspberry Pi.  The end user
connects to this to send and receive messages.

It requires Python 3, Flask, phonenumberslite, pyserial,
and the RPi.GPIO module.  In production deployments we use Gunicorn and
supervisord.  The frontend uses yarn for package management, with
bootstrap and webpack.

### Installation instructions

In production, files are placed in `/opt/pr-holonet/holonet-web`, with
log files and mailboxes placed in `/var/opt/pr-holonet`.

```
# As root:
apt-get install python3 python3-flask gunicorn3 python3-rpi.gpio supervisor \
    yarn
pip3 install phonenumberslite

mkdir -p /opt/pr-holonet
mkdir -p /var/opt/pr-holonet/log

# Place the holonet-web source code in /opt/pr-holonet/holonet-web.
cd /opt/pr-holonet/holonet-web
yarn install

ln -s /opt/pr-holonet/holonet-web/pr-holonet-web.conf /etc/supervisor/conf.d/
service supervisor reload
```

### Developer installation instructions

You can run the app using the Flask debug server.  If you don't have
a RockBLOCK attached and aren't running on a Raspberry Pi, then those
parts will just disable themselves.

We use pycodestyle, pylint, pytest, setuptools, webpack, and yarn.

```
# Create and activate a virtualenv if you want.
pip3 install --user flask phonenumberslite pycodestyle pylint pyserial \
    pytest RPi.GPIO setuptools

cd pr-holonet/holonet-web
yarn install

pycodestyle
python3 setup.py lint
python3 setup.py test

python3 app.py
```
