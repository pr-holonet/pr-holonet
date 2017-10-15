"""
    simple script to send a message using default class
    
"""

import rockBlock

from rockBlock import rockBlockProtocol


class MoExample_default(rockBlockProtocol):
    def main(self):
        rb = rockBlock.rockBlock("/dev/ttyUSB0", self)

        rb.sendMessage("Hello from Holonet! (test)")

        rb.close()

    def rockBlockTxStarted(self):
        print("rockBlockTxStarted")

    def rockBlockTxFailed(self):
        print("rockBlockTxFailed")

    def rockBlockTxSuccess(self, momsn):
        print("rockBlockTxSuccess " + str(momsn))


if __name__ == '__main__':
    MoExample_default().main()
