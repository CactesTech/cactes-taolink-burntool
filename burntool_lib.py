import os, sys, re
import logging, traceback
import time
import threading
from threading import Thread, Event, RLock
from queue import Queue, Empty
from enum import Enum, auto

import zlib

from burntool_timer import BurnToolTimer
from burntool_serial import BurnToolSerial, burn_tool_serial_get_ports
from burntool_util import intelhex_to_data_array

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
    UP_OPCODE_SECTOR_ERASE_ACK = 0x00D

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
    WAIT_ACK = auto()
    CONNECTED = auto()

class BurnToolRxStatus(Enum):
    HEAD = auto()
    DATA = auto()

class BurnToolEvent(Enum):
    POLLING = auto()
    DATA = auto()
    CONNECTED = auto()

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
        if opcode != BurnToolOpCode.UP_OPCODE_READ.value:
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

    def write_ram(self, address=0x0, data=b''):
        return self.pack(
            BurnToolOpCode.UP_OPCODE_WRITE_RAM.value,
            address,
            data
        )

    def write_ram_ack(self, address=0x0, data=b''):
        return self.pack(
            BurnToolOpCode.UP_OPCODE_WRITE_RAM_ACK.value,
            address,
            data
        )

    def execute_code(self, address=0x0, data=b''):
        return self.pack(
            BurnToolOpCode.UP_OPCODE_EXECUTE_CODE.value,
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

class BurnToolRxPkt:
    def __init__(self) -> None:
        self.opcodes = [v.value for _, v in BurnToolOpCode.__members__.items()]

        self.data = b''

        self.sta = BurnToolRxStatus.HEAD
        self.frm_opcode = None
        self.frm_addr = None
        self.frm_len = 0
        self.frm_data = b''

        self.timer = BurnToolTimer(self.timeout, 0.5)
        self.rxq = Queue()

    def timeout(self):
        self.timer.stop()

        self.data = b''

        self.sta = BurnToolRxStatus.HEAD

        self.frm_opcode = None
        self.frm_addr = None
        self.frm_len = 0
        self.frm_data_len = 0
        self.frm_data = b''

        logging.debug("timeout")

    def rx(self, data):
        self.data += data
        self.timer.start(0.5)
        while len(self.data) >= 7:
            if self.sta == BurnToolRxStatus.HEAD:
                while len(self.data) >= 7:
                    if self.data[0] in self.opcodes:
                        self.frm_opcode = self.data[0]
                        self.frm_addr = int.from_bytes(self.data[1:5], 'little')
                        self.frm_len = int.from_bytes(self.data[5:7], 'little')
                        self.sta = BurnToolRxStatus.DATA
                        self.data = self.data[7:]

                        self.frm_data_len = self.frm_len
                        if self.frm_opcode in [
                            BurnToolOpCode.UP_OPCODE_WRITE_RAM_ACK.value,
                            BurnToolOpCode.UP_OPCODE_WRITE_ACK.value,
                            BurnToolOpCode.UP_OPCODE_DISCONNECT_ACK.value,
                            BurnToolOpCode.UP_OPCODE_SECTOR_ERASE_ACK.value,
                            BurnToolOpCode.UP_OPCODE_CALC_CRC32_ACK.value,
                            BurnToolOpCode.UP_OPCODE_EXECUTE_CODE_END.value,
                            BurnToolOpCode.UP_OPCODE_CHANGE_BAUDRATE_ACK.value,
                            BurnToolOpCode.UP_OPCODE_BLOCK32K_ERASE_ACK.value,
                            BurnToolOpCode.UP_OPCODE_BLOCK64K_ERASE_ACK.value,
                        ]:
                            self.frm_data_len = 0

                        if self.frm_data_len == 0:
                            self.sta = BurnToolRxStatus.HEAD
                            self.rxq.put((self.frm_opcode, self.frm_addr, self.frm_len, b''))
                            self.timer.stop()
                        break
                    else:
                        self.data = self.data[1:]
            elif self.sta == BurnToolRxStatus.DATA:
                if len(self.data) >= self.frm_data_len:
                    self.sta = BurnToolRxStatus.HEAD
                    self.rxq.put((self.frm_opcode, self.frm_addr, self.frm_len, self.data[:self.frm_data_len]))
                    self.data = self.data[self.frm_data_len:]
                    self.timer.stop()
                else:
                    break


#---------------------------------------------------------------------------------------------
# Host
class BurnToolHost:
    def __init__(self, port, fw="fw.hex", patch="patch.bin"):
        self.port = port
        self.patch = f"{os.path.dirname(os.path.abspath(__file__))}/{patch}"
        self.fw = fw

        self.sta = BurnToolStatus.IDLE

        self.rxpkt = BurnToolRxPkt()
        self.frame = BurnToolFrame()
        self.evtq = Queue()

        self.steps = [
            (self.run_get_version, "get version"),
            (self.run_send_patch, "send patch"),
            (self.run_execute_code, "execute code"),
            (self.run_change_baud_rate, "change baud rate"),
            (self.run_erase_chip, "erase chip"),
            (self.run_program_flash, "program flash"),
            (self.run_crc_check, "crc check"),
            (self.run_execute_code, "execute code"),
            (self.run_disconnect, "disconnect"),
        ]

        self.wait_data = b''
        self.wait_ack = False

        self.fw_tail = bytes.fromhex('0104230051525251')
        self.fw_start_addr, self.fw_end_addr, self.fw_data = intelhex_to_data_array(self.fw)
        self.fw_crc = zlib.crc32(self.fw_data) & 0xFFFFFFFF

        logging.debug(f"fw: {self.fw_start_addr:08X} - {self.fw_end_addr:08X}, {len(self.fw_data)} bytes, crc: {self.fw_crc:08X}")

        self.serial = BurnToolSerial(self.on_received, self.on_failed)
        self.serial.start(port, 115200, 8, 1, 'None')

    def set_sta(self, sta):
        if sta == BurnToolStatus.IDLE:
            pass
        elif sta == BurnToolStatus.CONNECTED:
            if self.sta != sta:
                self.evtq.put(BurnToolEvent.CONNECTED)
        self.sta = sta
        logging.debug(f"set sta {sta}")

    def on_received(self, data):
        if self.sta == BurnToolStatus.IDLE:
            try:
                self.wait_data += data
                if self.wait_data.find('TurMass.'.encode('utf-8')) >= 0:
                    self.serial.write('TaoLink.'.encode('utf-8'))
                    self.wait_data = b''
                    self.wait_ack = True
                if self.wait_ack:
                    if self.wait_data.find('ok'.encode('utf-8')) >= 0:
                        self.set_sta(BurnToolStatus.CONNECTED)
                        self.wait_data = b''
            except:
                logging.error(f"{traceback.format_exc()}")
            logging.debug(f"on_received: {data}")
        elif self.sta == BurnToolStatus.CONNECTED:
            self.rxpkt.rx(data)

    def on_failed(self):
        logging.error(f"on_failed")
        os._exit(1)

    def request(self, opcode, address=0, msg=b'', timeout=0.5):
        data = self.frame.pack(opcode, address, msg)
        for _ in range(0, 3):
            self.serial.write(data)
            try:
                opcode, address, length, data = self.rxpkt.rxq.get(timeout=timeout)
                logging.info(f"rxpkt header: {opcode:02X}, 0x{address:08X}, {length}")
                if data:
                    logging.info(f"rxpkt data: {data.hex()}")
                return opcode, address, length, data
            except Empty:
                logging.warning("rxpkt timeout")
                continue
        return None, None, 0, b''

    def reqeust_change_baudrate(self):
        data = self.frame.pack(
        BurnToolOpCode.UP_OPCODE_CHANGE_BAUDRATE.value, 921600, b'')

        self.serial.write(data)
        time.sleep(0.050)
        self.rxpkt.timeout()

        self.serial.serial.baudrate = 921600

        opcode, address, length, data = self.request(
            BurnToolOpCode.UP_OPCODE_CHANGE_BAUDRATE.value,
            921600,
            timeout=0.6
        )
        if opcode != BurnToolOpCode.UP_OPCODE_CHANGE_BAUDRATE_ACK.value:
            self.serial.serial.baudrate = 115200
            return False
        return True

    def run_get_version(self):
        self.rxpkt.timeout()
        opcode, address, length, data = self.request(
            BurnToolOpCode.UP_OPCODE_GET_TYPE.value
        )
        if opcode != BurnToolOpCode.UP_OPCODE_SEND_TYPE.value:
            return False
        return True

    def run_send_patch(self):
        start_addr = 0x20080400
        with open(self.patch, 'rb') as f:
            patch = f.read()
            if len(patch) % 512 != 0:
                patch += b'\x00' * (512 - len(patch) % 512)
            logging.info(f"patch size {len(patch)}")
            for i in range(0, len(patch), 512):
                logging.info(f"patch addr {i}")
                opcode, address, length, data = self.request(
                    BurnToolOpCode.UP_OPCODE_WRITE_RAM.value,
                    start_addr + i,
                    patch[i:i+512],
                    timeout=2
                )
                if opcode != BurnToolOpCode.UP_OPCODE_WRITE_RAM_ACK.value:
                    return False
        return True

    def run_execute_code(self):
        opcode, address, length, data = self.request(
            BurnToolOpCode.UP_OPCODE_EXECUTE_CODE.value,
            0x20080400
        )
        if opcode != BurnToolOpCode.UP_OPCODE_EXECUTE_CODE_END.value:
            return False
        return True

    def run_erase_chip(self):
        start_addr = 0x00000000
        for i in range(4):
            opcode, address, length, data = self.request(
                BurnToolOpCode.UP_OPCODE_BLOCK64K_ERASE.value,
                start_addr
            )
            start_addr += 0x10000
            if opcode != BurnToolOpCode.UP_OPCODE_BLOCK64K_ERASE_ACK.value:
                return False
        return True

    def run_change_baud_rate(self):
        return self.reqeust_change_baudrate()

    def run_program_flash(self):
        sector_size = 256
        addr_oft = 0xC2000000
        last_page_addr = 0x0002FF00
        max_size = 0x0002FFF8
        tail = self.fw_tail

        start_addr, end_addr, fw = (self.fw_start_addr, self.fw_end_addr, self.fw_data.copy())

        logging.debug(f"fw: {start_addr:08X} - {end_addr:08X}, {len(fw)} bytes")

        start_addr -= addr_oft
        end_addr -= addr_oft

        # check firmware size
        if len(fw) > max_size:
            logging.error("fw size too large")
            return False

        # last sector
        if len(fw) > last_page_addr:
            fw_last_page = fw[last_page_addr:]
            fw = fw[:last_page_addr]
        else:
            fw_last_page = b''
            fw += b'\xFF' * ((sector_size - len(fw) % sector_size) % sector_size)
        fw_last_page += b'\xFF' * (sector_size - 8 - len(fw_last_page)) + tail

        logging.debug(f"aligned fw: {len(fw)} bytes, {len(fw) // sector_size} pages,{fw[-sector_size:].hex()}")
        logging.debug(f"aligned fw last page: {len(fw_last_page)}, {fw_last_page.hex()}")

        # fw area
        for i in range(len(fw) // sector_size):
            opcode, address, length, data = self.request(
                BurnToolOpCode.UP_OPCODE_WRITE.value,
                start_addr + i * sector_size,
                fw[i * sector_size:(i + 1) * sector_size]
            )
            if opcode != BurnToolOpCode.UP_OPCODE_WRITE_ACK.value:
                return False

        # the last page
        opcode, address, length, data = self.request(
            BurnToolOpCode.UP_OPCODE_WRITE.value,
            last_page_addr,
            fw_last_page
        )
        if opcode != BurnToolOpCode.UP_OPCODE_WRITE_ACK.value:
            return False

        return True

    def run_crc_check(self):
        start_addr = 0xc2000000
        data = len(self.fw_data).to_bytes(4, 'little') + b'\x00' * 4
        opcode, address, length, data = self.request(
            BurnToolOpCode.UP_OPCODE_CALC_CRC32.value,
            start_addr,
            data
        )
        if opcode != BurnToolOpCode.UP_OPCODE_CALC_CRC32_ACK.value:
            return False

        if address != self.fw_crc:
            logging.error(f"crc check failed: {address:08X} != {self.fw_crc:08X}")
            return False

        # check last 8 bytes
        option_bytes_addr = 0x00030000 - 8
        opcode, address, length, data = self.request(
            BurnToolOpCode.UP_OPCODE_READ.value,
            option_bytes_addr,
            b'\x00' * 8
        )

        if opcode != BurnToolOpCode.UP_OPCODE_READ_ACK.value:
            return False

        if data != self.fw_tail:
            return False

        return True

    def run_disconnect(self):
        opcode, address, length, data = self.request(
            BurnToolOpCode.UP_OPCODE_DISCONNECT.value
        )

        # DISCONNECT will always fail
        # if opcode != BurnToolOpCode.UP_OPCODE_DISCONNECT_ACK.value:
        #     return False

        return True

    def run_fail(self, msg):
        self.set_sta(BurnToolStatus.IDLE)
        logging.error(f"{msg}")

    def run(self):
        while True:
            try:
                evt = self.evtq.get(timeout=.05)
                if evt == BurnToolEvent.CONNECTED:
                    for i, v in enumerate(self.steps):
                        func, desp = v
                        if not func:
                            continue
                        if not func():
                            self.run_fail(f"{func.__name__} failed")
                            break
                        logging.info(f"step {i + 1}: {desp} ok")
                    break
            except Empty:
                continue
            except KeyboardInterrupt:
                break
        self.serial.stop()
        self.rxpkt.timer.destory()

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
                opcode, address, length, data = self.rxpkt.rxq.get(timeout=0.1)
                if opcode == BurnToolOpCode.UP_OPCODE_CHANGE_BAUDRATE.value:
                    self.serial.serial.baudrate = address
                    logging.info(f"change baudrate to {self.serial.serial.baudrate}")

                logging.info(f"rxpkt: {opcode:02X}, 0x{address:08X}, {length}")
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
