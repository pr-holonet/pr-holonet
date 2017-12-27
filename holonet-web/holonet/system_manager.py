'''

Copyright 2017 Hadi Esiely

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
contributors may be used to endorse or promote products derived from this
software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''

import codecs
import json
import logging
import os.path
import re
import subprocess
import sys

from holonet import queue_manager
from holonet.utils import mkdir_p, rm_f


AP_CONFIG_FILE = 'ap.json'
SYSTEM_MANAGER_ROOT = '/var/opt/pr-holonet/system_manager'
WPA_SUPPLICANT_CONF = '/etc/wpa_supplicant/wpa_supplicant.conf'
WLAN_DEVICE = 'wlan0'

# Will be overridden by app.py for non-Gunicorn builds.
system_manager_root = SYSTEM_MANAGER_ROOT

# Will be overridden by app.py for production builds.
safety_catch = True

_logger = logging.getLogger('holonet.system_manager')


# pylint: disable=unused-variable
def get_system_status():
    signal = queue_manager.last_known_signal_strength
    rockblock_serial = queue_manager.rockblock_serial_identifier or "Unknown"
    rockblock_status = queue_manager.last_known_rockblock_status
    rockblock_err = queue_manager.last_txfailed_mo_status

    network_mode = _get_network_mode()
    ap_settings = _get_ap_settings()
    (essid, wlan_mac, wlan_ip_addr) = _get_wlan_properties()
    wpa_props = _get_wpa_properties()

    result = dict(locals())
    result.update(ap_settings)
    del result['ap_settings']
    return result


def _get_network_mode():
    try:
        with open('/etc/dhcpcd.conf', 'r') as f:
            content = f.read()
    except FileNotFoundError:
        return 'unknown'
    if 'denyinterfaces %s' % WLAN_DEVICE in content:
        return 'ap'
    else:
        return 'client'


def _get_ap_settings():
    path = os.path.join(system_manager_root, AP_CONFIG_FILE)
    try:
        with open(path, 'r') as f:
            d = json.load(f)
    except Exception as err:
        d = {}

    def _f(n, v):
        if n not in d:
            d[n] = v
    _f('ap_enabled', False)
    _f('ap_name', 'holonet')
    _f('ap_password', 'holonet1')

    return d


def configure_network(settings):
    ssid = settings.get('ssid')
    psk = settings.get('psk')
    action = settings.get('action')
    if not ssid:
        return

    _run_cmd(['/bin/sed', '-i', '-n',
              '1 !H;1 h;$ {x;s/[[:space:]]*network={\\n[[:space:]]*'
              'ssid=%s[^}]*}//g;p;}' % json.dumps(ssid),
              WPA_SUPPLICANT_CONF], safe=True)

    if action == 'Delete':
        return

    with open(WPA_SUPPLICANT_CONF, 'a') as f:
        f.write('''
network={
    ssid=%s
''' % json.dumps(ssid))
        if psk:
            f.write('''
    psk=%s
    key_mgmt=WPA-PSK
''' % json.dumps(psk))
        f.write('''
}
''')

    _run_cmd(['/sbin/wpa_cli', 'reconfigure'], safe=True)


def set_ap_settings(settings):
    d = _get_ap_settings()

    def _f(n):
        v = settings.get(n)
        if v is not None:
            d[n] = v
    for k in ('ap_name', 'ap_password'):
        _f(k)

    d['ap_enabled'] = settings.get('ap_enabled', False)

    path = os.path.join(system_manager_root, AP_CONFIG_FILE)
    mkdir_p(system_manager_root)
    with open(path, 'w') as f:
        json.dump(d, f)

    if d['ap_enabled']:
        _enable_ap(d['ap_name'], d['ap_password'])
    else:
        _disable_ap()


def _get_wlan_properties():
    p = _run_cmd(['/sbin/wpa_cli', '-i', WLAN_DEVICE, 'status'], safe=True)
    if p is None or p.returncode != 0:
        return ('<Unknown>', '<Unknown>', '<Unknown>')
    out = p.stdout.decode('utf-8')
    return _extract_wlan_properties(out)


def _extract_wlan_properties(out):
    lines = out.split('\n')
    props = dict([l.split('=', 1) for l in lines if '=' in l])
    return (props.get('ssid', '<Unknown>'),
            props.get('address', '<Unknown>'),
            props.get('ip_address', '<Unknown>'))


def _get_wpa_properties():
    try:
        with open(WPA_SUPPLICANT_CONF, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        return {}
    return _extract_wpa_properties(content)


def _extract_wpa_properties(out):

    def _dequote(v):
        if v.startswith('"') and v.endswith('"'):
            return codecs.getdecoder('unicode_escape')(v[1:-1])[0]
        else:
            return v.strip()

    def _dequote_all(vs):
        return [_dequote(v) for v in vs]

    result = {}
    for match in re.finditer('network={([^}]+)}', out):
        block = match.group(1)
        lines = block.split('\n')
        props = dict([_dequote_all(l.split('=', 1))
                      for l in lines if '=' in l])
        if 'ssid' in props:
            ssid = props['ssid']
            other_props = dict(props)
            del other_props['ssid']
            result[ssid] = other_props
    return result


def _disable_ap():
    _stop_all_network_services()
    _rm_network_configs()

    _write_file('/etc/default/dnsmasq', '''
ENABLED=0
''')
    _write_file('/etc/dhcpcd.conf', '''
hostname
clientid
persistent
option rapid_commit
option domain_name_servers, domain_name, domain_search, host_name
option classless_static_routes
option ntp_servers
option interface_mtu
require dhcp_server_identifier
slaac private
''')
    _write_file('/etc/network/interfaces.d/%s' % WLAN_DEVICE, '''
allow-hotplug %s
iface %s inet dhcp
wpa-conf %s
''' % (WLAN_DEVICE, WLAN_DEVICE, WPA_SUPPLICANT_CONF))

    _run_cmd(['/sbin/ifup', WLAN_DEVICE], timeout=60)
    _run_cmd(['/usr/sbin/service', 'dhcpcd', 'start'], timeout=60)


def _enable_ap(ap_name, ap_password):
    _stop_all_network_services()
    _rm_network_configs()

    _write_file('/etc/default/dnsmasq', '''
ENABLED=1
CONFIG_DIR=/etc/dnsmasq.d,.dpkg-dist,.dpkg-old,.dpkg-new
''')
    _write_file('/etc/default/hostapd', '''
DAEMON_CONF='/etc/hostapd/hostapd.conf'
''')
    _write_file('/etc/hostapd/hostapd.conf', '''
interface=%s
driver=nl80211
ssid=%s
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=%s
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
''' % (WLAN_DEVICE, ap_name, ap_password))
    _write_file('/etc/dhcpcd.conf', '''
denyinterfaces %s
''' % WLAN_DEVICE)
    _write_file('/etc/dnsmasq.conf', '''
interface=%s
  dhcp-range=192.168.0.2,192.168.0.100,255.255.255.0,24h
''' % WLAN_DEVICE)
    _write_file('/etc/network/interfaces.d/%s' % WLAN_DEVICE, '''
allow-hotplug %s
iface %s inet static
    address 192.168.0.1
    netmask 255.255.255.0
    network 192.168.0.0
''' % (WLAN_DEVICE, WLAN_DEVICE))

    _run_cmd(['/sbin/ifup', WLAN_DEVICE], timeout=60)
    _run_cmd(['/usr/sbin/service', 'hostapd', 'start'], timeout=60)
    _run_cmd(['/usr/sbin/service', 'dnsmasq', 'start'], timeout=60)


def _stop_all_network_services():
    if safety_catch:
        _logger.debug(
            'Refusing _stop_all_network_services; safety catch is on.')
        return
    _run_cmd(['/usr/sbin/service', 'hostapd', 'stop'], timeout=60)
    _run_cmd(['/usr/sbin/service', 'dnsmasq', 'stop'], timeout=60)
    _run_cmd(['/usr/sbin/service', 'dhcpcd', 'stop'], timeout=60)
    _run_cmd(['/sbin/ifdown', WLAN_DEVICE], timeout=60)


def _rm_network_configs():
    if safety_catch:
        _logger.debug('Refusing _rm_network_configs; safety catch is on.')
        return
    files = [
        '/etc/default/dnsmasq',
        '/etc/default/hostapd',
        '/etc/dhcpcd.conf',
        '/etc/dnsmasq.conf',
        '/etc/hostapd/hostapd.conf',
        '/etc/network/interfaces.d/%s' % WLAN_DEVICE,
    ]
    for f in files:
        _logger.debug('rm -f %s', f)
        rm_f(f)


def _write_file(filename, content):
    if safety_catch:
        _logger.debug('Refusing _write_file(%s); safety catch is on.',
                      filename)
        return
    _logger.debug('%s: new content', filename)
    with open(filename, 'w') as f:
        f.write(content)


def _run_cmd(cmdline, safe=False, timeout=2):
    if not safe and safety_catch:
        _logger.debug('Refusing %s; safety catch is on.', ' '.join(cmdline))
        return
    _logger.debug('Running %s', ' '.join(cmdline))
    try:
        return subprocess.run(
            cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout)
    except FileNotFoundError:
        return None


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    _settings = {
        'ap_enabled': len(sys.argv) > 1 and bool(sys.argv[1])
    }
    safety_catch = False
    set_ap_settings(_settings)
