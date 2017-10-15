# pr-holonet

## holonet-web

This is the web service that runs on the Raspberry Pi.  The end user
connects to this to send and receive messages.

### Installation instructions

```
pip install --user flask

cd pr-holonet/holonet-web
ln -s ../../test_scripts/rockBlock.py holonet/
python app.py
```
