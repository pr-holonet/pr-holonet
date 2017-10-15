"""
    simple script to report signal strength using api function

"""

import rockBlock

from rockBlock import rockBlockProtocol


class SigStrengthExample_API(rockBlockProtocol):
    def main(self):
        rb = rockBlock.rockBlock("/dev/ttyUSB0", self)

        response = rb.get_signal_strength()
        print(response)

        rb.close()

    def rockBlockTxStarted(self):
        print("rockBlockTxStarted")

    def rockBlockTxFailed(self):
        print("rockBlockTxFailed")

    def rockBlockTxSuccess(self, momsn):
        print("rockBlockTxSuccess " + str(momsn))


if __name__ == '__main__':
    SigStrengthExample_API().main()
