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
