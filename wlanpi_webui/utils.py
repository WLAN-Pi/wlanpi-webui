from __future__ import annotations

import hashlib
import hmac
import os
import subprocess
import urllib.parse
from pathlib import Path
from time import time
from typing import Optional

import requests
from flask import current_app, redirect, request

SECRET_PATH = "/home/wlanpi/.local/share/wlanpi-core/secrets/shared_secret.bin"
SERVER = "127.0.0.1"
PORT = "31415"


def get_shared_secret(secret_path=SECRET_PATH) -> bytes:
    """Load shared secret from file."""
    if os.path.exists(secret_path):
        if os.access(secret_path, os.R_OK):
            return Path(secret_path).read_bytes()
    return b""


def generate_hmac_signature(
    method: str, endpoint: str, query: str = "", body: str = ""
) -> Optional[str]:
    """
    Generates HMAC signature for the request using SHA256.
    """
    secret = get_shared_secret()
    if not secret:
        return None
    canonical_string = f"{method}\n{endpoint}\n{query}\n{body}"
    current_app.logger.debug("WebUI canonical components:")
    current_app.logger.debug(f"Method: {method}")
    current_app.logger.debug(f"Path: {endpoint}")
    current_app.logger.debug(f"Query: {query}")
    current_app.logger.debug(f"Body: {body}")
    current_app.logger.debug(f"Hex: {canonical_string.encode().hex()}")
    return hmac.new(secret, canonical_string.encode(), hashlib.sha256).hexdigest()


def make_api_request(
    method: str, url: str, params: Optional[dict] = None, headers: Optional[dict] = None
) -> requests.Response:
    try:
        query_string = urllib.parse.urlencode(params) if params else ""
        endpoint = urllib.parse.urlparse(url).path
        body = ""

        signature = generate_hmac_signature(method, endpoint, query_string, body)

        headers = {
            "X-Request-Signature": signature,
            "accept": "application/json",
        }

        response = requests.post(url=url, headers=headers, params=params)
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        print(f"Error response: {e.response.text}")
        raise


wlanpi_core_warning = """
<script>
UIkit.notification({
    message: '<span uk-icon="icon: warning; ratio: 2"></span> wlanpi-core not running.',
    status: 'danger',
    pos: 'top-right',
    timeout: 10000
});
</script>
"""


def is_htmx(request):
    return request.headers.get("hx-request") == "true"


def get_service_down_message(service: str):
    return f"{service.capitalize()} service is unavailable or down."


def system_service_exists(service):
    """Check if a systemd service exists.
    Returns true if systemd service exists, false otherwise.

    $ /bin/systemctl list-unit-files wlanpi-grafana-scanner.service
    UNIT FILE                      STATE    VENDOR PRESET
    wlanpi-grafana-scanner.service disabled enabled

    1 unit files listed.
    $ echo $?
    0
    $ /bin/systemctl list-unit-files wlanpi-grafana-wipry.service
    UNIT FILE STATE VENDOR PRESET

    0 unit files listed.
    $ echo $?
    1
    """
    cmd = f"/bin/systemctl list-unit-files {service}.*"
    current_app.logger.info("subprocess is running %s", cmd)
    result = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL)
    if result.returncode == 0:
        return True
    return False


def system_service_running_state(service):
    """
    Checks the status of the systemd service.
    Returns true if systemd service is running, false otherwise.
    """
    try:
        # this cmd fails if service not installed
        cmd = f"/bin/systemctl is-active --quiet {service}"
        current_app.logger.info("subprocess is running %s", cmd)
        # check_returncode(): If returncode is non-zero, raise a CalledProcessError.
        subprocess.run(cmd, shell=True).check_returncode()
    except subprocess.CalledProcessError as exc:
        current_app.logger.info(
            "service %s is not running (error code: %s)", service, exc.returncode
        )
        return False
    return True


def run_command(cmd: list, suppress_output=False) -> str:
    """Run a single CLI command with subprocess and return stdout or stderr response"""
    cp = subprocess.run(
        cmd,
        encoding="utf-8",
        shell=False,
        check=False,
        capture_output=True,
    )

    if not suppress_output:
        if cp.stdout:
            return cp.stdout
        if cp.stderr:
            return cp.stderr

    return "completed process return code is non-zero with no stdout or stderr"


def systemd_service_message(service):
    """
    Checks if systemd service is running.
    Returns '<service> is running' if it is, and '<service> is not running' if not.
    """
    status = system_service_running_state(service)
    if status:
        return f"{service} is running"
    else:
        return f"{service} is not running"


def start_stop_service(task, service):
    """
    Starts or stops a service using wlanpi-core API.
    With HMAC authentication support.
    """
    params = {
        "name": f"{service}",
    }
    try:
        if task == "start":
            current_app.logger.info("starting %s", service)
            url = "http://127.0.0.1:31415/api/v1/system/service/start"
        elif task == "stop":
            current_app.logger.info("stopping %s", service)
            url = "http://127.0.0.1:31415/api/v1/system/service/stop"
        else:
            current_app.logger.error("Invalid task: %s", task)
            return redirect(request.referrer)

        response = make_api_request(method="POST", url=url, params=params)

        current_app.logger.info("Response status: %s", response.status_code)

        if response.status_code != 200:
            current_app.logger.error(
                "Request failed with status %s. Response body: %s",
                response.status_code,
                response.text,
            )
            current_app.logger.info(
                "systemd_service_message: %s",
                systemd_service_message("wlanpi-core"),
            )
            current_app.logger.info("%s generated %s response", url, response)

            # Add additional error context
            if response.status_code == 401:
                current_app.logger.error(
                    "Authentication failed. Verify HMAC configuration and shared secret access."
                )
            current_app.logger.info("%s generated %s response", url, response)
        return redirect(request.referrer)
    except requests.exceptions.RequestException:
        current_app.logger.exception("API request failed")
        return redirect(request.referrer)


def package_installed(package):
    version = get_apt_package_version(package)
    if version == "":
        return False
    return True


_package_cache: dict[str, tuple[str, float, float]] = {}
_dpkg_status_file = "/var/lib/dpkg/status"
CACHE_TTL = 60


def get_dpkg_status_mtime():
    try:
        return os.path.getmtime(_dpkg_status_file)
    except OSError:
        return 0


def get_apt_package_version(package) -> str:
    current_time = time()
    current_mtime = get_dpkg_status_mtime()

    if package in _package_cache:
        version, cache_time, cache_mtime = _package_cache[package]
        cache_age = current_time - cache_time

        if cache_mtime == current_mtime:
            if cache_age < CACHE_TTL:
                return version
            else:
                _package_cache[package] = (version, current_time, current_mtime)
                return version

    try:
        version = (
            subprocess.check_output(
                ["dpkg-query", "-W", "-f=${Version}", package],
                timeout=5,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        version = ""

    _package_cache[package] = (version, current_time, current_mtime)
    return version
