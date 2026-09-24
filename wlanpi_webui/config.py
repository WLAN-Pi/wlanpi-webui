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


# ponytail: cached for the life of the process; a hostname change needs a
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
    # Absolute session lifetime in seconds (default 12 hours), however active.
    MAX_SESSION_AGE = int(os.environ.get("WLANPI_WEBUI_MAX_SESSION_AGE", 12 * 60 * 60))
    # Persisted Flask signing key so a service restart does not sign users out
    # (a reboot still does, via the boot id check).
    SESSION_KEY_PATH = os.environ.get(
        "WLANPI_WEBUI_SESSION_KEY", "/var/lib/wlanpi-webui/session_key"
    )
    # Server-side registry of signed-in sessions, so logout and a password
    # change revoke a cookie instead of only deleting it from the browser.
    SESSION_STORE_PATH = os.environ.get(
        "WLANPI_WEBUI_SESSION_STORE", "/var/lib/wlanpi-webui/sessions.json"
    )
    # Hidden easter egg. Arming it is a device-wide flag file, written by
    # POST /beacon/arm and read at request time, so deleting the file disarms
    # it without a restart. It lives beside the session key.
    BEACON_FLAG_PATH = os.environ.get(
        "WLANPI_WEBUI_BEACON_FLAG", "/var/lib/wlanpi-webui/beacon"
    )
    # Game data, installed by the package (never committed to git).
    BEACON_DATA_PATH = os.environ.get(
        "WLANPI_WEBUI_BEACON_DATA", "/usr/share/wlanpi-webui/beacon/data.wad"
    )
    # Development overrides; never set these in production.
    BEACON_FORCE_UNLOCK = bool(os.environ.get("WLANPI_WEBUI_BEACON_FORCE_UNLOCK"))
    GAME_DEBUG = bool(os.environ.get("WLANPI_WEBUI_GAME_DEBUG"))
    # Live profiler runtime files, written by wlanpi-profiler for external
    # consumers. Read-only; absent when the profiler has never run or is down.
    PROFILER_STATUS_PATH = os.environ.get(
        "WLANPI_WEBUI_PROFILER_STATUS", "/run/wlanpi-profiler.status.json"
    )
    PROFILER_INFO_PATH = os.environ.get(
        "WLANPI_WEBUI_PROFILER_INFO", "/run/wlanpi-profiler.info.json"
    )
    # Persistent snapshot of the previous session (survives reboots).
    PROFILER_LAST_SESSION_PATH = os.environ.get(
        "WLANPI_WEBUI_PROFILER_LAST_SESSION",
        "/var/lib/wlanpi-profiler/last-session.json",
    )
    # Root-owned, argument-free wrapper that mints this WebUI's wlanpi-core
    # bearer token. The shared HMAC secret is root-only, so this is how the
    # unprivileged service gets a token.
    CORE_TOKEN_WRAPPER = os.environ.get(
        "WLANPI_WEBUI_CORE_TOKEN_WRAPPER",
        "/usr/libexec/wlanpi-webui/get-core-token",
    )
    # Speedtest results, stored server-side so the report page and the
    # results page can show past runs. Lives beside the session key.
    SPEEDTEST_RESULTS_PATH = os.environ.get(
        "WLANPI_WEBUI_SPEEDTEST_RESULTS",
        "/var/lib/wlanpi-webui/speedtest.json",
    )
