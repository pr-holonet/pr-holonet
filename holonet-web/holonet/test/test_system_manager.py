from unittest import TestCase

from holonet import system_manager


class TestSystemManager(TestCase):
    def test_extract_wlan_properties(self):
        def t(o, e):
            # pylint: disable=protected-access
            r = system_manager._extract_wlan_properties(o)
            self.assertEqual(r, e)

        example_output = '''
bssid=14:22:db:0c:8b:66
freq=2412
ssid=mynetwork
id=1
mode=station
pairwise_cipher=CCMP
group_cipher=CCMP
key_mgmt=WPA2-PSK
wpa_state=COMPLETED
ip_address=192.168.42.43
p2p_device_address=ba:27:eb:f7:5f:9d
address=b8:27:eb:f7:5f:9d
uuid=2c77dac3-ffb8-55fc-8da5-65bc211a49e7
'''
        t(example_output, ('mynetwork', 'b8:27:eb:f7:5f:9d', '192.168.42.43'))


    def test_extract_wpa_properties(self):
        def t(o, e):
            # pylint: disable=protected-access
            r = system_manager._extract_wpa_properties(o)
            self.assertEqual(r, e)

        example_output = '''
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=GB

network={
    ssid="ItsANetwork"
    psk="sshdontsay"
    key_mgmt=WPA-PSK
}

network={
    ssid="HiEveryone"
    psk="begone!"
    key_mgmt=WPA-PSK
}
'''
        t(example_output, {
            'ItsANetwork': {
                'psk': 'sshdontsay',
                'key_mgmt': 'WPA-PSK',
            },
            'HiEveryone': {
                'psk': 'begone!',
                'key_mgmt': 'WPA-PSK',
            },
        })
