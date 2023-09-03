#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
wlanpi_webui.config
~~~~~~~~~~~~~~~~~~~

globals that will be passed around the app
"""

import os
import socket
import subprocess

import psutil

from wlanpi_webui.__version__ import __version__


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


def get_interfaces() -> str:
    """Retrieve a list of interfaces found on host"""
    return list(psutil.net_if_addrs().keys())


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
                    wlanpi_version = "{0}".format(
                        line.split("=")[1].replace('"', "").strip()
                    )
    except OSError:
        pass
    return wlanpi_version


def get_apt_package_version(package) -> str:
    """Retrieve apt package version from apt-cache policy

    Installed example:
        $ apt-cache policy wlanpi-webui
        wlanpi-webui:
        Installed: 1.1.6-5
        Candidate: 1.1.6-5
        Version table:
        *** 1.1.6-5 500
                500 https://packagecloud.io/wlanpi/dev/debian bullseye/main arm64 Packages
                100 /var/lib/dpkg/status
            1.1.6-4 500
                500 https://packagecloud.io/wlanpi/dev/debian bullseye/main arm64 Packages

    Not installed example:
        $ apt-cache policy wlanpi-webui
        wlanpi-webui:
        Installed: (none)
        Candidate: 1.1.6-5
        Version table:
            1.1.6-5 500
                500 https://packagecloud.io/wlanpi/dev/debian bullseye/main arm64 Packages
            1.1.6-4 500
            500 https://packagecloud.io/wlanpi/dev/debian bullseye/main arm64 Packages
    """
    package_version = ""
    cmd = f"apt-cache policy {package}"
    apt_cache = subprocess.check_output(cmd, shell=True).decode()
    hit = False
    for match in apt_cache.lower().split("\n"):
        if "installed" in match:
            if "none" not in match:
                package_version = match
                hit = True
                break
    if hit:
        package_version = package_version.split(":")[1].strip()
    return package_version


def get_our_package_version() -> str:
    apt_version = get_apt_package_version("wlanpi-webui")
    print(f"{apt_version}")
    if apt_version:
        return apt_version
    return f"{__version__}"


class Config(object):
    WLANPI_VERSION = get_wlanpi_version()
    WEBUI_VERSION = get_our_package_version()
    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT")
    FILES_ROOT_DIR = "/var/www/html/"
    PROFILER_DIR = "/var/www/html/profiler/"
