import json
import logging
import os.path
import re
import subprocess

from holonet import queue_manager
from holonet.utils import mkdir_p, rm_f


AP_CONFIG_FILE = 'ap.json'
SYSTEM_MANAGER_ROOT = '/var/opt/pr-holonet/system_manager'
WLAN_DEVICE = 'wlan0'

# Will be overridden by app.py for non-Gunicorn builds.
system_manager_root = SYSTEM_MANAGER_ROOT

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
    (essid, wlan_mac) = _get_wlan_properties()

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
        return 'client'
    else:
        return 'ap'


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
    p = _run_cmd(['/sbin/iw', 'dev', WLAN_DEVICE, 'info'], safe=True)
    if p.returncode != 0:
        return ('<Unknown>', '<Unknown>')
    out = p.stdout.decode('utf-8')
    essid = _get_essid(out)
    wlan_mac = _get_wlan_mac(out)
    return (essid or '<Unknown>',
            wlan_mac or '<Unknown>')


def _get_essid(out):
    m = re.search('ssid (.*)', out)
    if m is None:
        return None
    return m.group(1)


def _get_wlan_mac(out):
    m = re.search('addr (.*)', out)
    if m is None:
        return "<Unknown>"
    return m.group(1)


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
wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf
''' % (WLAN_DEVICE, WLAN_DEVICE))

    _run_cmd(['/sbin/ifup', WLAN_DEVICE])
    _run_cmd(['/usr/sbin/service', 'dhcpcd', 'start'])


def _enable_ap(ap_name, ap_password):
    _stop_all_network_services()
    _rm_network_configs()

    _write_file('/etc/default/dnsmasq', '''
ENABLED=1
CONFIG_DIR=/etc/dnsmasq.d,.dpkg-dist,.dpkg-old,.dpkg-new
''' % WLAN_DEVICE)
    _write_file('/etc/default/hostapd', '''
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

    _run_cmd(['/sbin/ifup', WLAN_DEVICE])
    _run_cmd(['/usr/sbin/service', 'hostapd', 'start'])
    _run_cmd(['/usr/sbin/service', 'dnsmasq', 'start'])


def _stop_all_network_services():
    if safety_catch:
        _logger.debug(
            'Refusing _stop_all_network_services; safety catch is on.')
        return
    _run_cmd(['/usr/sbin/service', 'hostapd', 'stop'])
    _run_cmd(['/usr/sbin/service', 'dnsmasq', 'stop'])
    _run_cmd(['/usr/sbin/service', 'dhcpcd', 'stop'])
    _run_cmd(['/sbin/ifdown', WLAN_DEVICE])


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
        rm_f(f)


def _write_file(filename, content):
    if safety_catch:
        _logger.debug('Refusing _write_file(%s); safety catch is on.',
                      filename)
        return
    with open(filename, 'w') as f:
        f.write(content)


def _run_cmd(cmdline, safe=False, timeout=2):
    if not safe and safety_catch:
        _logger.debug('Refusing %s; safety catch is on.', ' '.join(cmdline))
        return
    return subprocess.run(
        cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout)
