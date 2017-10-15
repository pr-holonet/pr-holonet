"""
    simple script to report signal strength

"""

import rockBlock

from rockBlock import rockBlockProtocol


class SigStrengthExample_Default(rockBlockProtocol):
    def main(self):
        rb = rockBlock.rockBlock("/dev/ttyUSB0", self)

        response = rb.requestSignalStrength()
        print(response)
        
        rb.close()

    def rockBlockTxStarted(self):
        print("rockBlockTxStarted")

    def rockBlockTxFailed(self):
        print("rockBlockTxFailed")

    def rockBlockTxSuccess(self, momsn):
        print("rockBlockTxSuccess " + str(momsn))


if __name__ == '__main__':
    SigStrengthExample_Default().main()
