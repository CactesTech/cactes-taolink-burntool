import os
import sys
import time
import logging, traceback
import re
import queue
import threading

import serial
from serial.tools import list_ports

PARITY_DICT = {
    'None': serial.PARITY_NONE,
    'Even': serial.PARITY_EVEN,
    'Odd': serial.PARITY_ODD,
    'Mask': serial.PARITY_MARK,
    'Space': serial.PARITY_SPACE
}

def burn_tool_serial_get_ports():
    ports = []
    ports_name = [
        '/dev/ttyACM',
        '/dev/ttyUSB',
        'COM',
        '/dev/cu.'
    ]

    for comport in list_ports.comports():
        port = comport[0]
        for name in ports_name:
            if port.startswith(name):
                ports.append(port)
                break
    ports.sort()

    return ports

class BurnToolSerial(object):
    def __init__(self, on_received=None, on_failed=None):
        self.on_received = on_received
        self.on_failed = on_failed

        self.tx_queue = queue.Queue()
        self.rx_queue = queue.Queue()
        self.serial = None
        self.tx_thread = None
        self.rx_thread = None

        self.stop_event = threading.Event()

    def start(self, port, baud, bytesize, stopbits, parity, timeout=0):
        logging.debug(f"serial start, {port}/{baud}/{bytesize}/{stopbits}/{parity}")
        if self.serial:
            self.serial.close()

        try:
            self.serial = serial.Serial(port=port,
                                        baudrate=baud,
                                        bytesize=bytesize,
                                        stopbits=stopbits,
                                        parity=PARITY_DICT[parity],
                                        timeout=timeout)

            # Simulate a reset signal through RTS pin
            self.set_rts(False)
            time.sleep(0.01)
            self.serial.reset_input_buffer()
            self.set_rts(True)

            self.tx_queue.queue.clear()
            self.rx_queue.queue.clear()
            self.stop_event.set()
            self.tx_thread = threading.Thread(target=self._send)
            self.rx_thread = threading.Thread(target=self._recv)
            self.stop_event.clear()
            self.tx_thread.start()
            self.rx_thread.start()

        except IOError as e:
            logging.warning(f"{e} {traceback.format_exc()}")
            if self.on_failed:
                self.on_failed()

    def set_rts(self, value):
        if self.serial:
            self.serial.rts = value

    def stop(self):
        self.stop_event.set()
        if self.tx_thread:
            self.tx_thread.join()
            self.rx_thread.join()

        if self.serial:
            self.serial.close()

    def write(self, data):
        # logging.info("serial tx")
        self.serial.write(data)
        # logging.info(f'serial tx:{data.hex()}')

        # self.tx_queue.put(data)

    def read(self):
        return self.rx_queue.get()

    def _send(self):
        logging.info('tx thread is started')
        while not self.stop_event.is_set():
            try:
                data = self.tx_queue.get(True, 0.01)
                self.serial.write(data)
                # logging.debug(f'serial tx:{data.hex()}')
            except queue.Empty:
                continue
            except IOError as e:
                logging.warning(f"{e} {traceback.format_exc()}")
                self.serial.close()
                self.stop_event.set()
                if self.on_failed:
                    self.on_failed()

        logging.info('tx thread exits')

    def _recv(self):
        logging.info('rx thread is started')
        while not self.stop_event.is_set():
            try:
                data = self.serial.read(1)
                if data:
                    # logging.info(f'serial rx:{data.hex()}')
                    if self.on_received:
                        self.on_received(data)
                    else:
                        self.rx_queue.put(data)
            except IOError as e:
                logging.warning(f"{e} {traceback.format_exc()}")
                self.serial.close()
                self.stop_event.set()
                if self.on_failed:
                    self.on_failed()

        logging.info('rx thread exits')

