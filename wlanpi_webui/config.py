#!/usr/bin/python3

"""
wlanpi_webui.config
~~~~~~~~~~~~~~~~~~~

globals that will be passed around the app
"""

from __future__ import annotations

import os
import socket
from functools import lru_cache

import psutil

from wlanpi_webui.__version__ import __version__
from wlanpi_webui.utils import get_apt_package_version


def get_mac(interface: str) -> str:
    """Retrive 6 byte mac address for a given interface"""
    mac = ""
    ifaces = psutil.net_if_addrs()
    for i in ifaces:
        if interface == i:
            for snic in ifaces[interface]:
                if socket.AddressFamily.AF_PACKET in snic:
                    mac = snic.address.replace(":", "")
                    break
    return mac


def get_interfaces() -> list[str]:
    """Retrieve a list of interfaces found on host"""
    return list(psutil.net_if_addrs().keys())


# shortcut: cached for the life of the process; a hostname change needs a
# service restart, which is also how every other config value behaves.
@lru_cache(maxsize=1)
def get_hostname() -> str:
    """Retrieve system hostname for web interface"""
    hostname = socket.gethostname()
    # if hostname is the WLAN Pi default, attempt to return something more useful
    if hostname == "wlanpi":
        interface = "eth0"
        if interface in get_interfaces():
            hostname = get_mac(interface)
    return hostname


def get_wlanpi_version() -> str:
    """Retrieve wlanpi version from wlanpi-release for web interface"""
    wlanpi_version = ""
    try:
        with open("/etc/wlanpi-release") as _file:
            lines = _file.read().splitlines()
            for line in lines:
                if "VERSION" in line:
                    wlanpi_version = line.split("=")[1].replace('"', "").strip()
    except OSError:
        pass
    return wlanpi_version


def get_our_package_version() -> str:
    apt_version = get_apt_package_version("wlanpi-webui")
    if apt_version:
        return apt_version
    return f"{__version__}"


class Config:
    WLANPI_VERSION = get_wlanpi_version()
    WEBUI_VERSION = get_our_package_version()
    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT")
    FILES_ROOT_DIR = "/var/www/html/"
    PROFILER_DIR = "/var/www/html/profiler/"
    # Idle auto-logout window in seconds (default 4 hours). Any user activity
    # refreshes it; background polling does not.
    IDLE_TIMEOUT = int(os.environ.get("WLANPI_WEBUI_IDLE_TIMEOUT", 4 * 60 * 60))
    # Persisted Flask signing key so a service restart does not sign users out
    # (a reboot still does, via the boot id check).
    SESSION_KEY_PATH = os.environ.get(
        "WLANPI_WEBUI_SESSION_KEY", "/var/lib/wlanpi-webui/session_key"
    )
