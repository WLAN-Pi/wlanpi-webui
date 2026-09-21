from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import subprocess
import urllib.parse
from functools import lru_cache
from pathlib import Path
from time import time

import requests
from flask import current_app, redirect, request

SECRET_PATH = "/home/wlanpi/.local/share/wlanpi-core/secrets/shared_secret.bin"
CA_CERT = "/etc/nginx/ssl/self-signed-wlanpi.cert"
SERVER = "127.0.0.1"
PORT = "31415"


def get_shared_secret(secret_path=SECRET_PATH) -> bytes:
    """Load shared secret from file."""
    if os.path.exists(secret_path):
        if os.access(secret_path, os.R_OK):
            return Path(secret_path).read_bytes()
    return b""


# shortcut: cached for the life of the process; the boot id only changes on
# reboot, which restarts this service.
@lru_cache(maxsize=1)
def read_boot_id() -> str | None:
    """Return the current kernel boot id, or None when it cannot be read."""
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return None


def load_or_create_session_key(path: str) -> bytes:
    """Load the persisted Flask session key, creating it if needed.

    Falls back to a random per-process key when the path is unusable.
    """
    try:
        key_path = Path(path)
        if key_path.is_file():
            data = key_path.read_bytes()
            if len(data) >= 32:
                return data
        key = secrets.token_bytes(32)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        return key
    except OSError:
        return secrets.token_bytes(32)


def is_beacon_armed() -> bool:
    """True when the hidden page is armed on this device.

    Reads the flag at call time so deleting the file disarms it with no
    restart. A missing or unreadable flag degrades to disarmed, never an error.
    """
    if current_app.config.get("BEACON_FORCE_UNLOCK"):
        return True
    path = current_app.config.get("BEACON_FLAG_PATH")
    if not path:
        return False
    try:
        return Path(path).is_file()
    except OSError:
        current_app.logger.warning("beacon flag path unreadable: %s", path)
        return False


def set_beacon_armed() -> bool:
    """Write the arm flag. Returns True on success, False if unwritable."""
    path = current_app.config.get("BEACON_FLAG_PATH")
    if not path:
        return False
    try:
        flag = Path(path)
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("armed\n")
        return True
    except OSError:
        current_app.logger.warning("could not write beacon flag: %s", path)
        return False


def beacon_data_path() -> str | None:
    """Return the configured game data path if it exists on disk, else None."""
    path = current_app.config.get("BEACON_DATA_PATH")
    if not path:
        return None
    try:
        return path if Path(path).is_file() else None
    except OSError:
        return None


def get_safe_redirect_target(target: str | None) -> str:
    """
    Return a safe redirect target derived from the given URL-like string.

    Only relative paths without scheme or netloc are allowed. If the target is
    missing or unsafe, fall back to '/'.
    """
    # Default safe target
    default_target = "/"

    if not target:
        return default_target

    # Normalize backslashes that some browsers treat as path separators
    normalized = target.replace("\\", "/")

    parsed = urllib.parse.urlparse(normalized)

    # Disallow any URL that specifies a scheme (http, https, etc.) or netloc (host)
    if parsed.scheme or parsed.netloc:
        return default_target

    # Only allow absolute paths or empty paths; prevent open redirects via `//...`
    path = parsed.path or "/"
    if not path.startswith("/"):
        return default_target

    # Reconstruct the safe relative URL with query and fragment, if any
    safe = path
    if parsed.query:
        safe = f"{safe}?{parsed.query}"
    if parsed.fragment:
        safe = f"{safe}#{parsed.fragment}"

    return safe


def get_safe_referrer_target() -> str:
    """Safe redirect target for the current page's path.

    ``request.referrer`` is an absolute URL, which get_safe_redirect_target
    rejects; reduce it to its path first so callers return to the page they
    were on rather than the home page. htmx sends ``HX-Current-URL``, which is
    preferred when present.
    """
    source = request.headers.get("HX-Current-URL") or request.referrer or ""
    path = urllib.parse.urlparse(source).path
    return get_safe_redirect_target(path)


def generate_hmac_signature(
    method: str, endpoint: str, query: str = "", body: str = ""
) -> str | None:
    """
    Generates HMAC signature for the request using SHA256.
    """
    secret = get_shared_secret()
    if not secret:
        return None
    canonical_string = f"{method}\n{endpoint}\n{query}\n{body}"
    return hmac.new(secret, canonical_string.encode(), hashlib.sha256).hexdigest()


def make_api_request(
    method: str,
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    json_body: dict | None = None,
) -> requests.Response:
    try:
        query_string = urllib.parse.urlencode(params) if params else ""
        endpoint = urllib.parse.urlparse(url).path
        body = json.dumps(json_body) if json_body is not None else ""

        signature = generate_hmac_signature(method, endpoint, query_string, body)

        headers = {
            "X-Request-Signature": signature,
            "accept": "application/json",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=body,
            verify=CA_CERT,
            timeout=10,
        )
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        if e.response is not None:
            print(f"Error response: {e.response.text}")
        raise


CORE_API_BASE = f"https://{SERVER}:{PORT}"


def get_core_json(path: str, params: dict | None = None) -> dict | None:
    """GET a wlanpi-core API path, returning parsed JSON or None on failure."""
    try:
        data = make_api_request("GET", f"{CORE_API_BASE}{path}", params=params).json()
    except (requests.RequestException, ValueError):
        return None
    return data if isinstance(data, dict) else None


wlanpi_core_warning = """
<script>
wlanpiToast('<span uk-icon="icon: warning; ratio: 2"></span> wlanpi-core not running.', 'danger');
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
    cmd = ["/bin/systemctl", "list-unit-files", f"{service}.*"]
    current_app.logger.info("subprocess is running %s", cmd)
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL)
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
        cmd = ["/bin/systemctl", "is-active", "--quiet", service]
        current_app.logger.info("subprocess is running %s", cmd)
        # check_returncode(): If returncode is non-zero, raise a CalledProcessError.
        subprocess.run(cmd).check_returncode()
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


def run_pipeline(*commands, timeout: int = 10) -> str:
    """Run piped commands without a shell and return decoded stdout.

    Each argument is a command as a list, e.g.
    ``run_pipeline(["top", "-bn1"], ["awk", "{print $1}"])`` is the
    shell-free equivalent of ``top -bn1 | awk '{print $1}'``. Arguments are
    passed to each program directly, so there is no shell interpolation and
    no command injection is possible.
    """
    procs = []
    prev_stdout = None
    for command in commands:
        proc = subprocess.Popen(
            command,
            stdin=prev_stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if prev_stdout is not None:
            prev_stdout.close()  # let the upstream process receive SIGPIPE
        prev_stdout = proc.stdout
        procs.append(proc)
    out, _ = procs[-1].communicate(timeout=timeout)
    for proc in procs[:-1]:
        proc.wait(timeout=timeout)
    return out.decode()


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
    if task == "start" and not system_service_exists(service):
        return service_not_installed_warning(service)

    params = {
        "name": f"{service}",
    }
    try:
        if task == "start":
            current_app.logger.info("starting %s", service)
            url = "https://127.0.0.1:31415/api/v1/system/service/start"
        elif task == "stop":
            current_app.logger.info("stopping %s", service)
            url = "https://127.0.0.1:31415/api/v1/system/service/stop"
        else:
            current_app.logger.error("Invalid task: %s", task)
            return redirect(get_safe_referrer_target())

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
        return redirect(get_safe_referrer_target())
    except requests.exceptions.RequestException:
        current_app.logger.exception("API request failed")
        return redirect(get_safe_referrer_target())


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


def service_not_installed_warning(service_name):
    friendly_name = service_name
    # Clean up some common systemd service suffixes/prefixes for friendly display
    if friendly_name.endswith(".service"):
        friendly_name = friendly_name[:-8]
    if friendly_name.startswith("wlanpi-grafana-"):
        friendly_name = friendly_name.replace("wlanpi-grafana-", "Grafana ")
        friendly_name = friendly_name.replace("-", " ").title()
    elif friendly_name == "grafana-server":
        friendly_name = "Grafana"
    elif friendly_name == "wlanpi-profiler":
        friendly_name = "Profiler"
    elif friendly_name == "cockpit":
        friendly_name = "Cockpit"
    elif friendly_name == "kismet":
        friendly_name = "Kismet"
    else:
        friendly_name = friendly_name.replace("-", " ").title()

    return f"""
<script>
wlanpiToast('<span uk-icon="icon: warning; ratio: 2"></span> {friendly_name} is not installed.', 'warning');
</script>
"""
