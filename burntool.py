import os, sys, re
import logging, traceback
import time
import threading
from queue import Queue, Empty
from enum import Enum, auto

import fire
from burntool_serial import BurnToolSerial, burn_tool_serial_get_ports

class BurnToolOpCode(Enum):
    UP_OPCODE_GET_TYPE = 0x00
    UP_OPCODE_SEND_TYPE = 0x01

    UP_OPCODE_WRITE = 0x02
    UP_OPCODE_WRITE_ACK = 0x03

    UP_OPCODE_WRITE_RAM = 0x04
    UP_OPCODE_WRITE_RAM_ACK = 0x05

    UP_OPCODE_RSV1 = 0x06
    UP_OPCODE_RSV2 = 0x07

    UP_OPCODE_READ = 0x08
    UP_OPCODE_READ_ACK = 0x09

    UP_OPCODE_READ_RAM = 0x0A
    UP_OPCODE_READ_RAM_ACK = 0x0B

    UP_OPCODE_SECTOR_ERASE = 0x0C
    UP_OPCODE_BLOCK_ERASE_ACK = 0x00D

    UP_OPCODE_CHIP_ERASE = 0x0E
    UP_OPCODE_CHIP_ERASE_ACK = 0x0F

    UP_OPCODE_DISCONNECT = 0x10
    UP_OPCODE_DISCONNECT_ACK = 0x11

    UP_OPCODE_CHANGE_BAUDRATE = 0x12
    UP_OPCODE_CHANGE_BAUDRATE_ACK = 0x13

    UP_OPCODE_RSV5 = 0x14
    UP_OPCODE_EXECUTE_CODE = 0x15
    UP_OPCODE_RSV6 = 0x16
    UP_OPCODE_EXECUTE_CODE_END = 0x17
    UP_OPCODE_BOOT_RAM_ACK = 0x18

    UP_OPCODE_CALC_CRC32 = 0x19
    UP_OPCODE_CALC_CRC32_ACK = 0x1A

    UP_OPCODE_BLOCK32K_ERASE = 0x1B
    UP_OPCODE_BLOCK32K_ERASE_ACK = 0x1C
    UP_OPCODE_BLOCK64K_ERASE = 0x1D
    UP_OPCODE_BLOCK64K_ERASE_ACK = 0x1E

class BurnToolStatus(Enum):
    IDLE = auto()
    CONNECTED = auto()

class BurnToolRxStatus(Enum):
    HEAD = auto()
    DATA = auto()

class BurnToolEvent(Enum):
    POLLING = auto()
    DATA = auto()

class BurnToolFrame:
    def __init__(self):
        self.response_tab = {
            BurnToolOpCode.UP_OPCODE_GET_TYPE.value: self.send_type,
            BurnToolOpCode.UP_OPCODE_WRITE_RAM.value: self.write_ram_ack,
        }

    def pack(self, opcode, address=0, data=b''):
        msg = b''
        msg += opcode.to_bytes(1, 'little')
        msg += address.to_bytes(4, 'little')
        msg += int(len(data)).to_bytes(2, 'little')
        msg += data
        return msg

    def parse(self, frame):
        opcode = frame[0]
        address = int.from_bytes(frame[1:5], 'little')
        length = int.from_bytes(frame[5:7], 'little')
        data = frame[7:]

        logging.debug(f"parse frame: {opcode:02X}, 0x{address:08X}, {length}")

        return opcode, address, data

    def get_type(self):
        return self.pack(
            BurnToolOpCode.UP_OPCODE_GET_TYPE.value
        )

    def send_type(self, address=0x0, data=b''):
        return self.pack(
            BurnToolOpCode.UP_OPCODE_SEND_TYPE.value,
            0x00020101,
            b''
        )
    def write_ram_ack(self, address=0x0, data=b''):
        return self.pack(
            BurnToolOpCode.UP_OPCODE_WRITE_RAM_ACK.value,
            address,
            data
        )
    def response(self, frame):
        opcode, address, data = self.parse(frame)
        if opcode in self.response_tab.keys():
            return self.response_tab[opcode](address, data)
        else:
            logging.warning(f"unknown opcode: 0x{opcode:02X}")

    def to_bytes(self):
        return bytes([self.opcode]) + self.data

    @staticmethod
    def from_bytes(data):
        opcode = data[0]
        data = data[1:]
        return BurnToolFrame(opcode, data)

class BurnToolTimer:
    def __init__(self, callback):
        self.callback = callback
        self.timer = None

    def start(self, interval=0.5):
        logging.debug("start timer")
        if self.timer is not None:
            self.timer.cancel()
        self.timer = threading.Timer(interval, self.callback)
        self.timer.start()

    def stop(self):
        logging.debug("stop timer")
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

class BurnToolRxPkt:
    def __init__(self) -> None:
        self.opcodes = [v.value for _, v in BurnToolOpCode.__members__.items()]

        self.data = b''

        self.sta = BurnToolRxStatus.HEAD
        self.frm_opcode = None
        self.frm_addr = None
        self.frm_len = 0
        self.frm_data = b''

        self.timer = BurnToolTimer(self.timeout)
        self.rxq = Queue()

    def timeout(self):
        self.data = b''

        self.sta = BurnToolRxStatus.HEAD

        self.frm_opcode = None
        self.frm_addr = None
        self.frm_len = 0
        self.frm_data = b''

        logging.debug("timeout")

    def rx(self, data):
        self.data += data
        self.timer.start()
        while len(self.data) >= 7:
            if self.sta == BurnToolRxStatus.HEAD:
                while len(self.data) >= 7:
                    if self.data[0] in self.opcodes:
                        self.frm_opcode = self.data[0]
                        self.frm_addr = int.from_bytes(self.data[1:5], 'little')
                        self.frm_len = int.from_bytes(self.data[5:7], 'little')
                        self.sta = BurnToolRxStatus.DATA
                        self.data = self.data[7:]
                        if self.frm_len == 0:
                            self.sta = BurnToolRxStatus.HEAD
                            self.rxq.put((self.frm_opcode, self.frm_addr, self.frm_len, b''))
                            self.timer.stop()
                        break
                    else:
                        self.data = self.data[1:]
            elif self.sta == BurnToolRxStatus.DATA:
                if len(self.data) >= self.frm_len:
                    self.sta = BurnToolRxStatus.HEAD
                    self.rxq.put((self.frm_opcode, self.frm_addr, self.frm_len, self.data[:self.frm_len]))
                    self.data = self.data[self.frm_len:]
                    self.timer.stop()
                else:
                    break


#---------------------------------------------------------------------------------------------
# Host
class BurnToolHost:
    def __init__(self, port, patch="patch.bin"):
        self.port = port
        self.patch = patch

        self.sta = BurnToolStatus.IDLE
        self.rxsta = BurnToolRxStatus.HEAD
        self.rxdata = b''
        self.data = b''
        self.rxlen = 0
        self.frame = BurnToolFrame()
        self.timer = BurnToolTimer()

        self.rxq = Queue()

        self.serial = BurnToolSerial(self.on_received, self.on_failed)
        self.serial.start(port, 115200, 8, 1, 'None')

    def set_sta(self, sta):
        if sta == BurnToolStatus.IDLE:
            pass
        elif sta == BurnToolStatus.CONNECTED:
            self.rxsta = BurnToolRxStatus.HEAD
            self.rxdata = b''
            self.rxlen = 0
        self.sta = sta
        logging.debug(f"set sta {sta}")

    def on_received(self, data):
        if self.sta == BurnToolStatus.IDLE:
            try:
                data = data.decode('utf-8')
                logging.debug(f"{data}")
                if 'TurMass.' in data:
                    self.serial.write('TaoLink.'.encode('utf-8'))
                if 'ok' in data:
                    self.set_sta(BurnToolStatus.CONNECTED)
            except:
                logging.error(f"{traceback.format_exc()}")
        elif self.sta == BurnToolStatus.CONNECTED:
            self.rxdata += data
            if self.rxsta == BurnToolRxStatus.HEAD:
                if len(self.rxdata) >= 7:
                    self.frame.parse(self.rxdata[:7])
                    self.rxdata = self.rxdata[7:]
                    self.rxsta = BurnToolRxStatus.DATA

        logging.debug(f"on_received: {data}")

    def on_failed(self):
        logging.error(f"on_failed")

    def burn(self, target):
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break
        self.serial.stop()

#---------------------------------------------------------------------------------------------
# Device
class BurnToolDevice:
    def __init__(self, port):
        self.port = port
        self.serial = BurnToolSerial(self.on_received, self.on_failed)
        self.serial.start(port, 115200, 8, 1, 'None')
        self.sta = BurnToolStatus.IDLE
        self.rxsta = BurnToolRxStatus.HEAD
        self.rxdata = b''
        self.rxlen = 0
        self.frame = BurnToolFrame()

        self.ts = int(time.time() * 1000)
        self.lock = threading.Lock()

    def set_sta(self, sta):
        self.sta = sta
        logging.debug(f"set sta {sta}")

    def evt(self, event, data=b''):
        now = int(time.time() * 1000)
        self.lock.acquire()
        if self.sta == BurnToolStatus.IDLE:
            if event == BurnToolEvent.DATA:
                try:
                    data = data.decode('utf-8')
                    logging.debug(f"{data}")
                    if 'TaoLink.' in data:
                        self.serial.write('ok'.encode('utf-8'))
                        self.set_sta(BurnToolStatus.CONNECTED)
                except:
                    logging.error(f"{traceback.format_exc()}")
            else:
                if now - self.ts > 50:
                    self.serial.write('TurMass.'.encode('utf-8'))
                    self.ts = now
        elif self.sta == BurnToolStatus.CONNECTED:
            if event == BurnToolEvent.DATA:
                rsp = self.frame.response(data)
                if rsp:
                    self.serial.serial.write(rsp)
        self.lock.release()

    def on_received(self, data):
        self.evt(BurnToolEvent.DATA, data)

    def on_failed(self):
        logging.error(f"on_failed")

    def run(self):
        while True:
            try:
                self.evt(BurnToolEvent.POLLING)
                time.sleep(0.01)
            except KeyboardInterrupt:
                break
        self.serial.stop()

#---------------------------------------------------------------------------------------------
# Parser
class BurnToolParser:
    def __init__(self, port):
        self.opcodes = [v.value for _, v in BurnToolOpCode.__members__.items()]
        logging.debug(f"opcodes: {self.opcodes}")

        self.port = port

        self.serial = BurnToolSerial(self.on_received, self.on_failed)
        self.serial.start(port, 115200, 8, 1, 'None')

        self.rxpkt = BurnToolRxPkt()

    def on_received(self, data):
        self.rxpkt.rx(data)

    def on_failed(self):
        logging.error(f"on_failed")

    def run(self):
        while True:
            try:
                opcode, addr, length, data = self.rxpkt.rxq.get(timeout=0.1)
                logging.info(f"rxpkt: {opcode:02X}, 0x{addr:08X}, {length}")
                if data:
                    logging.info(f"rxpkt data: {data.hex()}")
            except Empty:
                continue
            except KeyboardInterrupt:
                break
        self.serial.stop()

    def timeout(self):
        self.sta = BurnToolRxStatus.HEAD
        self.remained_length = 0
        self.data = b''
        logging.debug("timeout")

def base16_to_bin(in_file, out_file):
    data = b''
    with open(in_file, 'r') as f:
        for line in f:
            data += bytes.fromhex(line)

    with open(out_file, 'wb') as f:
        f.write(data)

def carr_to_bin(in_file, out_file):
    data = b''
    with open(in_file, 'r') as f:
        for line in f:
            if '0x' in line:
                x = line.strip().replace(',', '')[2:]
                print(f"{x}")
                res = bytes.fromhex(x)[::-1]
                print(f"res: {res.hex()}")
                data += res
    with open(out_file, 'wb') as f:
        f.write(data)

if __name__ == '__main__':
    # logging.basicConfig(
    #     filename="burntool.log",
    #     level=logging.DEBUG,
    #     format='%(asctime)s - %(levelname)s - %(message)s'
    # )

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    fire.Fire({
        "host": BurnToolHost,
        "device": BurnToolDevice,
        "parser": BurnToolParser,
        "base16_to_bin": base16_to_bin,
        "carr_to_bin": carr_to_bin,
    })
