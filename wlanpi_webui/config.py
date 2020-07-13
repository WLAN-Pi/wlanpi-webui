# -*- encoding: utf-8 -*-
import os
from wlanpi_webui.__version__ import __version__

def get_wlanpi_version():
    wlanpi_version = ""
    try:
        with open("/etc/wlanpi-release") as _file:
            lines = _file.read().splitlines()
            for line in lines:
                if "VERSION" in line:
                    wlanpi_version = "{0}".format(
                        line.split("=")[1].replace('"', "").strip()
                    )
    except OSError:
        pass
    return wlanpi_version

class Config(object):
    WLANPI_VERSION = get_wlanpi_version() 
    WEBUI_VERSION = f"{__version__}" 
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
