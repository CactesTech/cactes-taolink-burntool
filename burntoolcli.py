import logging
import fire

from burntool_lib import BurnToolHost, BurnToolDevice, BurnToolParser
from burntool_util import base16_to_bin, carr_to_bin

if __name__ == '__main__':
    # logging.basicConfig(
    #     level=logging.DEBUG,
    #     format='%(asctime)s - %(levelname)s - %(message)s'
    # )

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    fire.Fire({
        "host": BurnToolHost,
        "device": BurnToolDevice,
        "parser": BurnToolParser,
        "base16_to_bin": base16_to_bin,
        "carr_to_bin": carr_to_bin,
    })
