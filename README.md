# pr-holonet

| Pi pin # | Pi pin desc        | RockBLOCK pin # | RockBLOCK pin desc  |
|----------|--------------------|-----------------|---------------------|
| 2        | 5V power           | 8               | Power               |
| 6        | Ground             | 7               | Ground              |
| 8        | UART TX            | 2               | UART RX             |
| 10       | UART RX            | 3               | UART TX             |
| 12       | GPIO 18 (PCM\_CLK) |                 | RI (Ring Indicator) |
| 14       | Ground             |                 |                     |
| 16       | GPIO 23            |                 |                     |

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
