import re
import subprocess

from holonet import queue_manager


def get_system_status():
    signal = queue_manager.last_known_signal_strength
    rockblock_serial = queue_manager.rockblock_serial_identifier or "Unknown"
    rockblock_status = queue_manager.last_known_rockblock_status
    rockblock_err = queue_manager.last_txfailed_mo_status

    (essid, wlan_mac) = _get_wlan_properties()

    return dict(locals())


def _get_wlan_properties():
    p = _run_cmd(['/sbin/iw', 'dev', 'wlan0', 'info'])
    if p.returncode != 0:
        return ('<Unknown>', '<Unknown>')
    out = p.stdout.decode('utf-8')
    essid = _get_essid(out)
    wlan_mac = _get_wlan_mac(out)
    return (essid or '<Unknown>',
            wlan_mac or '<Unknown>')


def _get_essid(out):
    print(out)
    m = re.search('ssid (.*)', out)
    if m is None:
        return None
    return m.group(1)


def _get_wlan_mac(out):
    m = re.search('addr (.*)', out)
    if m is None:
        return "<Unknown>"
    return m.group(1)


def _run_cmd(cmdline, timeout=2):
    return subprocess.run(
        cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout)
