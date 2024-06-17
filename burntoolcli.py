import logging
import fire

from burntool_lib import BurnToolHost, BurnToolDevice, BurnToolParser
from burntool_util import base16_to_bin, carr_to_bin

if __name__ == '__main__':
    fire.Fire({
        "host": BurnToolHost,
        "device": BurnToolDevice,
        "parser": BurnToolParser,
        "base16_to_bin": base16_to_bin,
        "carr_to_bin": carr_to_bin,
    })
