import hashlib
import hmac
import os
import subprocess
from functools import wraps
from typing import Optional

import requests
from flask import current_app, redirect, request


class HMACAuth:
    """Handle HMAC authentication for API calls."""

    def __init__(self):
        self._requires_hmac = False
        self._shared_secret: Optional[str] = None

    @property
    def requires_hmac(self) -> bool:
        return self._requires_hmac

    @requires_hmac.setter
    def requires_hmac(self, value: bool):
        self._requires_hmac = value

    def get_shared_secret(self) -> Optional[str]:
        """Get shared secret from file, caching the result."""
        if self._shared_secret is None:
            secret_path = "/opt/wlanpi-core/.secrets/shared_secret"
            try:
                if not os.path.exists(secret_path):
                    current_app.logger.error(
                        "Secret file does not exist: %s", secret_path
                    )
                    return None

                if not os.access(secret_path, os.R_OK):
                    current_app.logger.error(
                        "No read permission for secret file: %s", secret_path
                    )
                    return None

                with open(secret_path, "r") as f:
                    self._shared_secret = f.read().strip()
                current_app.logger.debug(
                    "Successfully loaded shared secret from %s", secret_path
                )

            except IOError as e:
                current_app.logger.error("IO error reading shared secret: %s", str(e))
                return None
            except Exception as e:
                current_app.logger.error(
                    "Unexpected error accessing shared secret: %s", str(e)
                )
                return None

        return self._shared_secret

    def generate_signature(
        self, method: str, endpoint: str, payload: str = ""
    ) -> Optional[str]:
        """Generate HMAC signature for request."""
        secret = self.get_shared_secret()
        if not secret:
            return None

        canonical_string = f"{method}\n{endpoint}\n{payload}"
        signature = hmac.new(
            secret.encode(), canonical_string.encode(), hashlib.sha256
        ).hexdigest()

        return signature


hmac_auth = HMACAuth()


def with_hmac_retry(func):
    """Decorator to handle HMAC authentication with retry logic."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not hmac_auth.requires_hmac:
            response = func(*args, **kwargs)
            if (
                response.status_code == 401
                and "X-Requires-Signature" in response.headers
            ):
                current_app.logger.info(
                    "Signature required, retrying with HMAC signature"
                )
                hmac_auth.requires_hmac = True
                return func(*args, **kwargs)
            return response
        return func(*args, **kwargs)

    return wrapper


def make_api_request(
    method: str, url: str, params: Optional[dict] = None, headers: Optional[dict] = None
) -> requests.Response:
    """Make API request with optional HMAC authentication."""
    if hmac_auth.requires_hmac:
        headers = headers or {}
        endpoint = url.split("localhost:31415")[-1]
        payload = ""
        signature = hmac_auth.generate_signature(method, endpoint, payload)

        if signature:
            headers["X-Request-Signature"] = signature

    try:
        response = requests.request(
            method=method, url=url, params=params, headers=headers
        )
        return response
    except requests.exceptions.RequestException as e:
        current_app.logger.error("API request failed: %s", str(e))
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
    current_app.logger.debug("subprocess is running %s", cmd)
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
        current_app.logger.debug("subprocess is running %s", cmd)
        # check_returncode(): If returncode is non-zero, raise a CalledProcessError.
        subprocess.run(cmd, shell=True).check_returncode()
    except subprocess.CalledProcessError as exc:
        # cmd failed, so systemd service not installed
        current_app.logger.debug(
            "service %s, error code %s, output %s", service, exc.returncode
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


@with_hmac_retry
def start_stop_service(task, service):
    """
    Starts or stops a service using wlanpi-core API.
    With HMAC authentication support.
    """
    headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
    }
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
        start_url = "http://127.0.0.1:31415/api/v1/system/service/start"
        response = make_api_request(
            method="POST", url=url, params=params, headers=headers
        )
        if response.status_code != 200:
            current_app.logger.info(
                "systemd_service_message: %s",
                systemd_service_message("wlanpi-core"),
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
