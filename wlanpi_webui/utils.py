from __future__ import annotations

import json
import math
import os
import secrets
import subprocess
import urllib.parse
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from time import CLOCK_BOOTTIME, clock_gettime, time

import requests
from flask import current_app, redirect, request, session

CA_CERT = "/etc/nginx/ssl/self-signed-wlanpi.cert"
SERVER = "127.0.0.1"
PORT = "31415"
TOKEN_TIMEOUT = 15


class CoreAuthError(requests.RequestException):
    """Could not authenticate to wlanpi-core (token mint or clock)."""


# Cached wlanpi-core bearer token. Per process: the service runs a single
# gunicorn worker, and a fresh token is minted on demand after a 401.
_token: dict[str, str | None] = {"value": None}

# Last wlanpi-core authentication problem, surfaced by the navbar alert icon
# and the /alerts page. Diagnostic state, not a ledger.
_core_alert: dict[str, str | None] = {"value": None}


def record_core_alert(message: str) -> None:
    """Remember a core authentication failure for the alerts page."""
    _core_alert["value"] = message


def clear_core_alert() -> None:
    """Clear the remembered core authentication failure."""
    _core_alert["value"] = None


# ponytail: cached for the life of the process; the boot id only changes on
# reboot, which restarts this service.
@lru_cache(maxsize=1)
def read_boot_id() -> str | None:
    """Return the current kernel boot id, or None when it cannot be read."""
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return None


def boot_clock() -> float:
    """Seconds since boot, for session and backoff timing.

    Unlike time(), wall-clock steps (NTP sync on a Pi with no RTC, ``date -s``)
    cannot stretch it, and every process on the device shares it. Sessions end
    at reboot anyway (boot id check), so restarting from 0 then is harmless.
    """
    return clock_gettime(CLOCK_BOOTTIME)


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


def get_core_token(force=False) -> str:
    """Return a wlanpi-core JWT, minting one via the root-owned wrapper.

    The shared HMAC secret is root-only, so the WebUI (which runs unprivileged
    as ``wlanpi``) cannot sign requests. It runs the fixed, argument-free
    wrapper in ``CORE_TOKEN_WRAPPER`` as root instead, which mints a token for
    its own device id.
    """
    if _token["value"] and not force:
        return _token["value"]

    wrapper = current_app.config["CORE_TOKEN_WRAPPER"]
    try:
        result = subprocess.run(
            ["sudo", "-n", wrapper],
            capture_output=True,
            text=True,
            timeout=TOKEN_TIMEOUT,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        current_app.logger.error("core token wrapper failed: %s", exc)
        record_core_alert("Could not mint a wlanpi-core token.")
        raise CoreAuthError("Could not mint a wlanpi-core token.") from exc

    # getjwt prints a JSON object; tolerate any surrounding output.
    start = result.stdout.find("{")
    end = result.stdout.rfind("}")
    token = ""
    if start != -1 and end > start:
        try:
            token = str(
                json.loads(result.stdout[start : end + 1]).get("access_token") or ""
            )
        except ValueError:
            token = ""
    if not token:
        current_app.logger.error(
            "core token wrapper returned no token: %s", result.stdout
        )
        record_core_alert("Could not mint a wlanpi-core token.")
        raise CoreAuthError("Could not mint a wlanpi-core token.")

    clear_core_alert()
    _token["value"] = token
    return token


def reset_core_token() -> None:
    """Forget the cached token so the next request mints a fresh one."""
    _token["value"] = None


def _clock_not_set(response: requests.Response) -> bool:
    try:
        return bool(response.json().get("error") == "AUTH_CLOCK_NOT_SET")
    except ValueError:
        return False


def make_api_request(
    method: str,
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    json_body: dict | None = None,
) -> requests.Response:
    """Call wlanpi-core with a bearer token, re-minting once on 401."""
    body = json.dumps(json_body) if json_body is not None else ""
    request_headers = dict(headers or {})
    request_headers["accept"] = "application/json"
    if json_body is not None:
        request_headers["Content-Type"] = "application/json"

    def _send(token: str) -> requests.Response:
        return requests.request(
            method=method,
            url=url,
            headers={**request_headers, "Authorization": f"Bearer {token}"},
            params=params,
            data=body,
            verify=CA_CERT,
            timeout=10,
        )

    response = _send(get_core_token())
    if response.status_code == 401:
        # the token expired or was revoked; mint a fresh one and retry once
        response = _send(get_core_token(force=True))

    if response.status_code == 503 and _clock_not_set(response):
        record_core_alert("NTP needs set; cannot proceed")
        raise CoreAuthError("NTP needs set; cannot proceed")

    response.raise_for_status()
    clear_core_alert()
    return response


# Health-derived alerts are refreshed at most once per TTL so the navbar bell
# and the after_request hook do not probe wlanpi-core on every request.
_health_cache: list[dict[str, str]] = []
_health_cache_at = 0.0
HEALTH_CACHE_TTL = 60


def _health_alerts() -> list[dict[str, str]]:
    """Throttling, clock, and failed-unit alerts from wlanpi-core, cached."""
    global _health_cache, _health_cache_at

    now = time()
    if now - _health_cache_at < HEALTH_CACHE_TTL:
        return list(_health_cache)

    alerts: list[dict[str, str]] = []

    health = get_core_json("/api/v1/system/health")
    if health:
        throttled = health.get("throttled") or {}
        if throttled.get("undervoltage"):
            alerts.append(
                {
                    "key": "throttle-undervoltage",
                    "title": "Under-voltage detected",
                    "detail": "The WLAN Pi is being under-powered, which can "
                    "cause instability and data loss.",
                    "fix": "Use the supplied power supply and cable.",
                }
            )
        elif (
            throttled.get("throttled")
            or throttled.get("frequency_capped")
            or throttled.get("soft_temperature_limit")
        ):
            alerts.append(
                {
                    "key": "throttle",
                    "title": "Device is throttling",
                    "detail": "The CPU is throttled, frequency-capped, or "
                    "hitting the soft temperature limit.",
                    "fix": "Check cooling and power.",
                }
            )

        ntp = health.get("ntp") or {}
        if ntp.get("enabled") and not ntp.get("synchronized"):
            alerts.append(
                {
                    "key": "ntp-unsynced",
                    "title": "Clock is not synchronised",
                    "detail": "NTP is enabled but the clock has not synced "
                    "(timedatectl reports NTP=yes, NTPSynchronized=no).",
                    "fix": "sudo timedatectl set-ntp true",
                }
            )

    failed = get_core_json("/api/v1/system/services/failed")
    if failed:
        units = failed.get("units") or []
        if units:
            names = ", ".join(str(unit.get("unit", "")) for unit in units)
            alerts.append(
                {
                    "key": "failed-services",
                    "title": f"{len(units)} failed systemd unit(s)",
                    "detail": names,
                    "fix": "systemctl --failed",
                }
            )

    _health_cache = alerts
    _health_cache_at = now
    return list(alerts)


def active_alerts(core_running: bool) -> list[dict[str, str]]:
    """Conditions worth surfacing in the navbar bell and on the alerts page."""
    alerts: list[dict[str, str]] = []

    if not core_running:
        alerts.append(
            {
                "key": "core-down",
                "title": "wlanpi-core is not running",
                "detail": "Login and most WebUI features depend on wlanpi-core.",
                "fix": "sudo systemctl start wlanpi-core.socket wlanpi-core",
            }
        )

    message = _core_alert["value"]
    if message:
        alerts.append(
            {
                "key": "core-auth",
                "title": "wlanpi-core authentication failed",
                "detail": message,
                "fix": "Check the clock (sudo timedatectl set-ntp true), then "
                "mint a token: sudo getjwt wlanpi-webui",
            }
        )

    if core_running:
        alerts.extend(_health_alerts())

    return alerts


CORE_API_BASE = f"https://{SERVER}:{PORT}"


def get_core_json(path: str, params: dict | None = None) -> dict | None:
    """GET a wlanpi-core API path, returning parsed JSON or None on failure."""
    try:
        data = make_api_request("GET", f"{CORE_API_BASE}{path}", params=params).json()
    except (requests.RequestException, ValueError):
        return None
    return data if isinstance(data, dict) else None


def post_core_json(
    path: str, json_body: dict | None = None, params: dict | None = None
) -> dict | None:
    """POST to a wlanpi-core API path, returning parsed JSON or None on failure."""
    try:
        response = make_api_request(
            "POST", f"{CORE_API_BASE}{path}", params=params, json_body=json_body
        )
        data = response.json()
    except (requests.RequestException, ValueError):
        return None
    return data if isinstance(data, dict) else None


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


def system_service_running_state(service, quiet=False):
    """
    Checks the status of the systemd service.
    Returns true if systemd service is running, false otherwise.

    ``quiet`` suppresses the INFO logs, for callers that poll frequently.
    """
    try:
        # this cmd fails if service not installed
        cmd = ["/bin/systemctl", "is-active", "--quiet", service]
        if not quiet:
            current_app.logger.info("subprocess is running %s", cmd)
        # check_returncode(): If returncode is non-zero, raise a CalledProcessError.
        subprocess.run(cmd).check_returncode()
    except subprocess.CalledProcessError as exc:
        if not quiet:
            current_app.logger.info(
                "service %s is not running (error code: %s)", service, exc.returncode
            )
        return False
    return True


def system_service_active_state(service, timeout=5) -> str:
    """Return the raw ``systemctl is-active`` state for a service.

    Unlike ``system_service_running_state`` this distinguishes the transitional
    states (``activating``/``deactivating``) from ``inactive``, so a UI can say
    "starting" instead of "stopped" while a slow service boots.
    """
    cmd = ["/bin/systemctl", "is-active", service]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return (result.stdout or "").strip() or "unknown"


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


def service_friendly_name(service_name):
    """Human-readable name for a systemd service."""
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
    return friendly_name


def queue_toast(message, status="primary"):
    """Queue a one-shot toast, delivered by the after_request hook.

    Survives the redirect that start/stop returns, so the toast lands on the
    page the user is sent back to.
    """
    session["wlanpi_toast"] = {"message": message, "status": status}


def start_stop_service(task, service, label=None, noun="service"):
    """
    Starts or stops a service using wlanpi-core API, queuing a toast with the
    result.

    ``label`` overrides the friendly name (used for Grafana data streams, whose
    systemd unit name is not the name shown to the user) and ``noun`` names what
    is being toggled, e.g. "service" or "data stream".
    """
    name = label or service_friendly_name(service)

    if task == "start" and not system_service_exists(service):
        queue_toast(f"{name} {noun} is not installed.", "warning")
        return redirect(get_safe_referrer_target())

    if not system_service_running_state("wlanpi-core"):
        queue_toast("wlanpi-core is not running.", "danger")
        return redirect(get_safe_referrer_target())

    if task not in ("start", "stop"):
        current_app.logger.error("Invalid task: %s", task)
        return redirect(get_safe_referrer_target())

    current_app.logger.info("%sing %s", task, service)
    url = f"https://127.0.0.1:31415/api/v1/system/service/{task}"
    params = {"name": service}

    try:
        response = make_api_request(method="POST", url=url, params=params)
    except requests.exceptions.RequestException:
        current_app.logger.exception("API request failed")
        queue_toast(f"Could not {task} {name} {noun}.", "warning")
        return redirect(get_safe_referrer_target())

    if response.status_code != 200:
        current_app.logger.error(
            "Request failed with status %s. Response body: %s",
            response.status_code,
            response.text,
        )
        if response.status_code == 401:
            current_app.logger.error("Authentication failed. Verify core credentials.")
        queue_toast(f"Could not {task} {name} {noun}.", "warning")
        return redirect(get_safe_referrer_target())

    queue_toast(
        f"{name} {noun} {'started' if task == 'start' else 'stopped'}.", "success"
    )
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


SPEEDTEST_RESULT_LIMIT = 20
SPEEDTEST_NOTE_MAX = 200

SPEEDTEST_NUMBER_FIELDS = (
    "download_mbps",
    "upload_mbps",
    "ping_ms",
    "jitter_ms",
    "loaded_ping_ms",
    "loaded_jitter_ms",
    "download_min_mbps",
    "download_max_mbps",
    "upload_min_mbps",
    "upload_max_mbps",
    "download_mb",
    "upload_mb",
    "duration_s",
)


def _speedtest_number(value) -> float | None:
    """Coerce a client-supplied number, or None if it is not usable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return round(number, 3)


def format_speedtest_tested_at(value) -> str:
    """Render a stored ISO timestamp as local 'YYYY-MM-DD HH:MM'.

    Results are stored in UTC, and older ones in that same shape, so this
    formats at display time and returns anything it cannot parse untouched.
    """
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except (AttributeError, TypeError, ValueError):
        return str(value) if value else ""


def load_speedtest_results() -> list[dict]:
    """Read the stored speedtest results, newest first."""
    path = current_app.config.get("SPEEDTEST_RESULTS_PATH")
    if not path:
        return []
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def save_speedtest_result(payload) -> dict | None:
    """Validate and store a speedtest result. None if the payload is unusable."""
    if not isinstance(payload, dict):
        return None

    result: dict = {
        "id": f"{int(time())}-{secrets.token_hex(3)}",
        "tested_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "client_ip": str(payload.get("client_ip") or "")[:64],
        "note": "",
    }
    for field in SPEEDTEST_NUMBER_FIELDS:
        value = _speedtest_number(payload.get(field))
        if value is not None:
            result[field] = value

    # a result with no throughput at all is not worth keeping
    if "download_mbps" not in result and "upload_mbps" not in result:
        return None

    path = current_app.config.get("SPEEDTEST_RESULTS_PATH")
    if not path:
        return None

    results = load_speedtest_results()
    results.insert(0, result)
    del results[SPEEDTEST_RESULT_LIMIT:]

    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(results))
        tmp.replace(target)
    except OSError:
        current_app.logger.warning("could not store speedtest result: %s", path)
        return None
    return result


def get_speedtest_result(result_id: str) -> dict | None:
    """Return one stored result by id, or None."""
    return next((r for r in load_speedtest_results() if r.get("id") == result_id), None)


def set_speedtest_note(result_id: str, note: str) -> bool:
    """Attach a short note to a stored result. False if the result is unknown."""
    path = current_app.config.get("SPEEDTEST_RESULTS_PATH")
    if not path:
        return False

    results = load_speedtest_results()
    for result in results:
        if result.get("id") == result_id:
            result["note"] = note[:SPEEDTEST_NOTE_MAX]
            break
    else:
        return False

    try:
        target = Path(path)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(results))
        tmp.replace(target)
    except OSError:
        current_app.logger.warning("could not store speedtest note: %s", path)
        return False
    return True
