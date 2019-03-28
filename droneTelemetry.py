#!/usr/bin/env python2
# Version 1.0 FINAL

import urwid
import argparse

from sys import exit, argv
from multiprocessing import Process, Queue
from stat import S_ISFIFO
from os import stat
from os import write
from os import close


class DecoderSymaX5SW():
    """
    Extracted from https://github.com/chopengauer/nrf_analyze
    Modified for better performance and adaptations for write only Address and data
    """
    def __init__(self, internalDataPipe, gnuRadioPipe):

        self.internalDataPipe = internalDataPipe
        self.gnuRadioPipe = open(gnuRadioPipe, 'rb')

        self.runDecoderLoop()

    def crc2_add(self, c):
        global crc2
        crc2 ^= c << 15
        crc2 <<= 1
        if (crc2 > 0xffff):
            crc2 &= 0xffff
            crc2 ^= 0x1021

        return crc2

    def make_byte(self, s):
        byte = s[0] << 7 | s[1] << 6 | s[2] << 5 | s[3] << 4 | s[4] << 3 | s[5] << 2 | s[6] << 1 | s[7]
        return byte

    def runDecoderLoop(self):

        global crc2
        p_buff = []
        pay_len = 10
        addr_len = 5

        while True:

            if len(p_buff) >= 329:

                preamb = self.make_byte(p_buff[0:8])

                if (preamb == 0xAA) or (preamb == 0x55):

                    buf3 = p_buff[8:329]
                    p_addr = ''

                    ## Address
                    for k in range(addr_len):
                        p_addr = p_addr + chr(self.make_byte(buf3[k * 8: k * 8 + 8]))

                    ## PCF
                    p5_len = self.make_byte([0,0] + buf3[addr_len * 8: addr_len * 8 + 6])

                    ## Data
                    p2_data = ''
                    if p5_len >= 32:
                        p5_len_c = 32
                    else:
                        p5_len_c = p5_len

                    for k in range (pay_len):
                        p2_data = p2_data + chr(self.make_byte(buf3[(addr_len + k) * 8: (addr_len + 1 + k) * 8]))

                    ## crc
                    p2_crc8 = self.make_byte(buf3[(addr_len + pay_len) * 8: (addr_len + pay_len + 1) * 8])
                    p2_crc = (p2_crc8 << 8) + self.make_byte(buf3[(addr_len + pay_len + 1) * 8:(addr_len + pay_len + 2) * 8])

                    ## calc crc
                    crc2 = 0xffff
                    for k in range ((addr_len + 1 + p5_len_c) * 8 + 1):
                        self.crc2_add(buf3[k])
                    crc2 = 0xffff

                    for k in range ((addr_len + pay_len) * 8):
                        self.crc2_add(buf3[k])
                    p2_crc_calc = crc2

                    addr = ''.join("{:02x}".format(ord(c)) for c in p_addr)
                    p2ata = ''.join("{:02x}".format(ord(c)) for c in p2_data)
                    p2crc = p2_crc

                    if p2_crc == p2_crc_calc:
                        # print "Address " + addr  + "\tData " + p2ata + "\tCRC "+ format(p2crc,'04x') + "\tLen " + str(pay_len) + ' \tpreamb = ' + format(preamb,'02x')
                        write(self.internalDataPipe, addr + '|' + p2ata)

                del p_buff[0]

            else:
                buf = self.gnuRadioPipe.read(4096)
                if not buf:
                    print '[*] Broken PIPE - Restart Script'
                    break
                for bit in buf:
                    p_buff.append(ord(bit))


class DisplayDrone:

    def __init__(self):

        # Colors palette
        self._palette = [
             ('pg normal', 'white', 'black', 'standout'),
             ('pg complete', 'white', 'dark green'),
             ('pg smooth', 'dark magenta', 'black'),
             ('text activate', 'light green', 'black'),
             ('text enabled', 'white', 'dark blue')
             ]

        # Frame components
        self.text = urwid.Text('Engine Power:','left')

        self.progressBar = urwid.ProgressBar(
            'pg normal',
            'pg complete',
            satt='pg smooth')

        self.header = urwid.Columns(
            [self.text, self.progressBar])

        self.footer = urwid.Text('[*] Waiting for packages...')

        # Movement indicators
        self.forwardText = urwid.Text(('pg normal','Forward'))
        self.forwardMap = urwid.AttrMap(self.forwardText, '')
        self.forward = urwid.Padding(
            self.forwardMap,
            'right',
            ('relative', 75))

        self.fallbackText = urwid.Text(('pg normal','Fallback'))
        self.fallbackMap = urwid.AttrMap(self.fallbackText, '')
        self.fallback = urwid.Padding(
            self.fallbackMap,
            'right',
            ('relative', 75))

        self.leftText = urwid.Text(('pg normal','Left'))
        self.left =  urwid.AttrMap(self.leftText, '')

        self.rightText = urwid.Text(('pg normal','Right'))
        self.right = urwid.AttrMap(self.rightText, '')

        self.columnsLeftRight = urwid.Columns(
            [self.left, self.right])

        self.movementIndicators = urwid.Frame(
            urwid.Filler(self.columnsLeftRight),
            self.forward,
            self.fallback)

        # Movement in site
        self.turnLeftText = urwid.Text(('pg normal','Turn Left'), 'left')
        self.turnLeft = urwid.AttrMap(self.turnLeftText, '')

        self.turnRightText = urwid.Text(('pg normal','Turn Right'), 'right')
        self.turnRight = urwid.AttrMap(self.turnRightText, '')

        # Container all movements componenents
        self.body = urwid.Columns(
                [self.turnLeft, urwid.BoxAdapter(self.movementIndicators, 5), self.turnRight])

        # Container for all components
        self.frame = urwid.Frame(
            urwid.Filler(self.body),
            self.header,
            self.footer)

        #Component father.
        self.display = urwid.LineBox(self.frame,'Syma X5SW Telemetry Display')
        self.mainLoop = urwid.MainLoop(self.display, self._palette, unhandled_input=self.inputQuit)

    def inputQuit(self, key):
        # Clean quit...
        if key is 'q' or key is 'Q':
            close(self.internalDataPipe)
            self.decoderProcess.terminate()
            exit(0)

    def setDecoderProcess(self, subProcess):
        #Reference to Subprocess for kill them with 'Q' key
        self.decoderProcess = subProcess

    def processData(self, data):

        def resetComponents():
            self.forwardText.set_text(('pg normal', 'Forward'))
            self.fallbackText.set_text(('pg normal', 'Fallback'))
            self.turnLeftText.set_text(('pg normal', 'Turn Left'))
            self.turnRightText.set_text(('pg normal', 'Turn Right'))
            self.leftText.set_text(('pg normal', 'Left'))
            self.rightText.set_text(('pg normal', 'Right'))
            self.progressBar.set_completion(0)

        # Data is the package of Drone: address + data
        listData = data.split('|')
        # Split to hexa values strings
        dataPackage = [listData[1][i:i + 2] for i in range(0, len(listData[1]), 2)]
        address = listData[0]

        # Set State: waiting for binding
        if dataPackage[0] == '88' and dataPackage[2] == '88':
            self.footer.set_text(('text activate', '[*] Waiting for binding!!!'))
            resetComponents()
            self.mainLoop.draw_screen()
            return

        # Set State: Decoding packages from address...
        self.footer.set_text(('text activate', '[*] Decoding Packages - Drone Address: ' + address))

        # Set engine power
        self.progressBar.set_completion( (int(dataPackage[0], 16) * 100) / 255 )

        # Check pitch
        if dataPackage[1] != '00':
            # Convert hexa string to binary and get most significant bit.
            pitch = bin(int('1' + dataPackage[1], 16))[3:][0]
            if pitch == '1':
                self.fallbackText.set_text(('text activate', 'FALLBACK'))
            else:
                self.forwardText.set_text(('text activate', 'FORWARD'))
        else:
            self.forwardText.set_text(('pg normal', 'Forward'))
            self.fallbackText.set_text(('pg normal', 'Fallback'))

        # Check rudder
        if dataPackage[2] != '00':
            # Convert hexa string to binary and get most significant bit.
            rudder = bin(int('1' + dataPackage[2], 16))[3:][0]
            if rudder == '1':
                self.turnRightText.set_text(('text activate', 'Turn RIGHT'))
            else:
                self.turnLeftText.set_text(('text activate', 'TURN LEFT'))
        else:
            self.turnLeftText.set_text(('pg normal', 'Turn Left'))
            self.turnRightText.set_text(('pg normal', 'Turn Right'))

        # Check aileron
        if dataPackage[3] != '00':
            # Convert hexa string to binary and get most significant bit.
            aileron = bin(int('1' + dataPackage[3], 16))[3:][0]
            if aileron == '1':
                self.rightText.set_text(('text activate', 'RIGHT'))
            else:
                self.leftText.set_text(('text activate', 'LEFT'))
        else:
            self.leftText.set_text(('pg normal', 'Left'))
            self.rightText.set_text(('pg normal', 'Right'))

        self.mainLoop.draw_screen()

    def create_pipe(self):
        # Create pipe for share data between decoder and Display.
        self.internalDataPipe =  self.mainLoop.watch_pipe(self.processData)
        return self.internalDataPipe

    def run(self):
        self.mainLoop.run()

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Syma X5SW Telemetry Display and Decoder')
    parser.add_argument('gnuRadiopipe', help='Pipe with GNU Radio data packages')
    args = parser.parse_args()

    gnuRadioPipe = args.gnuRadiopipe
    displaydrone = DisplayDrone()
    internalDataPipe = displaydrone.create_pipe()

    if not S_ISFIFO(stat(gnuRadioPipe).st_mode):
        print '[!!!] Parameter must be a PIPE with Gnuradio Data from Transmitter'
        exit(-1)

    processDecoder = Process(target=DecoderSymaX5SW, args=(internalDataPipe, gnuRadioPipe))
    displaydrone.setDecoderProcess(processDecoder)

    processDecoder.start()
    displaydrone.run()
