"""
    simple script to send a message
"""

import rockBlock

from rockBlock import rockBlockProtocol

class MoExample (rockBlockProtocol):

    def main(self):
        rb = rockBlock.rockBlock("/dev/ttyUSB0", self)

        rb.sendMessage("Hello from Holonet! (test)")      

        rb.close()


    def rockBlockTxStarted(self):
        print("rockBlockTxStarted")


    def rockBlockTxFailed(self):
        print("rockBlockTxFailed")


    def rockBlockTxSuccess(self,momsn):
        print("rockBlockTxSuccess " + str(momsn))

   
if __name__ == '__main__':
    MoExample().main()
