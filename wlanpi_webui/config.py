#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
wlanpi_webui.config
~~~~~~~~~~~~~~~~~~~

globals that will be passed around the app
"""

import os
import socket

import psutil

from wlanpi_webui.__version__ import __version__


def get_mac(interface: str) -> str:
    """retrive 6 byte mac address for a given interface"""
    mac = ""
    ifaces = psutil.net_if_addrs()
    for i in ifaces:
        if interface == i:
            for snic in ifaces[interface]:
                if socket.AddressFamily.AF_PACKET in snic:
                    mac = snic.address.replace(":", "")
                    break
    return mac


def get_interfaces() -> str:
    """retrieve a list of interfaces found on host"""
    return list(psutil.net_if_addrs().keys())


def get_hostname() -> str:
    """retrieve system hostname for web interface"""
    hostname = socket.gethostname()
    # if hostname is the WLAN Pi default, attempt to return something more useful
    if hostname == "wlanpi":
        interface = "eth0"
        if interface in get_interfaces():
            hostname = get_mac(interface)
    return hostname


def get_wlanpi_version() -> str:
    """retrieve wlanpi version from wlanpi-release for web interface"""
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
    HOSTNAME = get_hostname()
    TITLE = f"WLAN Pi: {HOSTNAME}"
    WLANPI_VERSION = get_wlanpi_version()
    WEBUI_VERSION = f"{__version__}"
    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT")
