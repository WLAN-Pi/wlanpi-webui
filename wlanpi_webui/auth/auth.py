#!/usr/bin/python3

"""wlanpi_webui.auth.auth

PAM-backed session login for the WLAN Pi WebUI.

The WebUI runs unprivileged as the ``wlanpi`` user, so it cannot run the PAM
conversation itself for other users. It brokers authentication through the
root-running wlanpi-core ``/api/v1/auth/pam`` endpoints (localhost only; the
WebUI sends its reserved ``wlanpi-webui`` bearer token). Passwords are never
persisted or logged.
"""

from __future__ import annotations

import fcntl
import hmac
import json
import os
import secrets
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

import requests
from flask import (
    abort,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from wlanpi_webui.auth import bp
from wlanpi_webui.config import get_hostname
from wlanpi_webui.utils import boot_clock, make_api_request, read_boot_id

CORE_PAM_URL = "https://127.0.0.1:31415/api/v1/auth/pam"
CORE_PAM_CHANGE_URL = f"{CORE_PAM_URL}/change"

# Failed-login backoff: FREE_ATTEMPTS misses per client IP or username, then
# the wait doubles from 1s up to MAX_DELAY. A key is forgotten after an hour
# without failures, and at most MAX_TRACKED keys are kept.
FREE_ATTEMPTS = 5
MAX_DELAY = 300
FORGET_AFTER = 3600
MAX_TRACKED = 4096

# Core statuses (and core HTTP errors, see _core_status) shown to the user.
MESSAGES = {
    None: "Unable to reach wlanpi-core. Is the service running?",
    "failure": "Incorrect username or password.",
    "invalid_input": (
        "Enter a username (up to 128 characters) and a password (up to 512 characters)."
    ),
    "rate_limited": "wlanpi-core is busy. Wait a minute and try again.",
    "unavailable": "wlanpi-core could not check the password. Check its logs.",
    "password_rejected": (
        "The new password is too short, too simple, or too similar to the "
        "current one. Choose a longer, less predictable password."
    ),
}
_CORE_HTTP_ERRORS = {422: "invalid_input", 429: "rate_limited", 503: "unavailable"}
# Statuses that count as a failed guess for the backoff.
_FAILED_GUESS = ("failure", "invalid_input")


def init_auth(app) -> None:
    """Attach the session registry cache and the failed-login counters.

    The registry's source of truth is the SESSION_STORE_PATH file, so every
    gunicorn worker (including the overlap during a HUP reload) sees the same
    sessions and a restart keeps users signed in. ponytail: the failed-login
    counters stay in process memory; a restart forgets them.
    """
    app.extensions["wlanpi_auth"] = {
        "lock": threading.Lock(),
        "sessions": {},
        "stamp": None,
        "failures": {},
    }


def _state() -> dict:
    state: dict = current_app.extensions["wlanpi_auth"]
    return state


def _store_path() -> Path:
    return Path(current_app.config["SESSION_STORE_PATH"])


def _stamp(path: Path) -> tuple[int, int, int] | None:
    """Identify one version of the store file (each write is a new inode)."""
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_ino, st.st_mtime_ns, st.st_size)


def _read_store(path: Path) -> dict:
    """Load the registry; records from another boot or malformed ones are dropped."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("boot_id") != read_boot_id():
        return {}
    sessions = data.get("sessions")
    if not isinstance(sessions, dict):
        return {}
    return {
        sid: rec
        for sid, rec in sessions.items()
        if isinstance(rec, dict) and isinstance(rec.get("created"), (int, float))
    }


def _sessions() -> dict:
    """The registry, re-read whenever the store file changed on disk."""
    state = _state()
    stamp = _stamp(_store_path())
    if stamp is not None and stamp != state["stamp"]:
        state["sessions"] = _read_store(_store_path())
        state["stamp"] = stamp
    sessions: dict = state["sessions"]
    return sessions


@contextmanager
def _file_lock(path: Path):
    """Serialize registry writers across processes (best effort)."""
    try:
        fh = open(f"{path}.lock", "a")
    except OSError:
        fh = None
    try:
        if fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
        yield
    finally:
        if fh:
            fh.close()


def _write_store(path: Path, sessions: dict) -> None:
    """Replace the store file atomically.

    If that fails, delete the file instead: a stale copy could bring a revoked
    session back after a restart, while a missing one only signs everyone out.
    """
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".sessions.")
        with os.fdopen(fd, "w") as fh:
            json.dump({"boot_id": read_boot_id(), "sessions": sessions}, fh)
        os.replace(tmp, path)
        return
    except OSError as exc:
        current_app.logger.error("could not write sessions to %s: %s", path, exc)
    if tmp:
        Path(tmp).unlink(missing_ok=True)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        current_app.logger.error("could not remove stale %s: %s", path, exc)


@contextmanager
def _update_sessions():
    """Read-modify-write the registry under the thread and file locks."""
    state = _state()
    path = _store_path()
    with state["lock"], _file_lock(path):
        sessions = dict(_sessions())
        yield sessions
        max_age = current_app.config["MAX_SESSION_AGE"]
        now = boot_clock()
        for sid in [s for s, r in sessions.items() if now - r["created"] > max_age]:
            del sessions[sid]
        _write_store(path, sessions)
        # This process's copy is authoritative until the file changes again;
        # never fall back to a stale file that the write could not replace.
        state["sessions"] = sessions
        state["stamp"] = _stamp(path)


def session_is_valid() -> bool:
    """True if the cookie's session id is registered and within its lifetime."""
    record = _sessions().get(session.get("sid"))
    if not record or record.get("user") != session.get("user"):
        return False
    age = boot_clock() - record["created"]
    return bool(age <= current_app.config["MAX_SESSION_AGE"])


def end_session() -> None:
    """Revoke the current session server-side and clear the cookie."""
    sid = session.get("sid")
    if sid in _sessions():
        with _update_sessions() as sessions:
            sessions.pop(sid, None)
    session.clear()


def get_csrf_token() -> str:
    """Return the current session's CSRF token, creating it on demand."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf() -> bool:
    """True if the request carries the session's CSRF token."""
    sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    expected = session.get("csrf_token", "")
    if not (expected and sent):
        return False
    # Compare bytes: compare_digest raises TypeError on non-ASCII str.
    return hmac.compare_digest(sent.encode(), expected.encode())


def csrf_required(f):
    """Reject requests without a valid CSRF token."""

    def wrapper(*args, **kwargs):
        if not validate_csrf():
            abort(400, description="Missing or invalid CSRF token")
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


def hx_post_anchor(
    url: str, inner: str, target: str | None = None, css: str = ""
) -> str:
    """Build an htmx POST anchor carrying the CSRF token for ``url``."""
    token = get_csrf_token()
    swap = f' hx-target="{target}" hx-swap="innerHTML"' if target else ""
    cls = f' class="{css}"' if css else ""
    return (
        f'<a hx-post="{url}" hx-indicator=".progress"{swap}{cls} '
        f'hx-headers=\'{{"X-CSRF-Token": "{token}"}}\'>{inner}</a>'
    )


def service_toggle_anchor(
    running: bool, start: str, stop: str, target: str = "#content"
) -> str:
    """Start/Stop button for a systemd-backed service."""
    if running:
        return hx_post_anchor(
            stop, "Stop", target=target, css="uk-button uk-button-default"
        )
    return hx_post_anchor(
        start, "Start", target=target, css="uk-button uk-button-primary"
    )


def _core_status(url: str, body: dict) -> str | None:
    """POST to a core PAM endpoint; returns its status, an error key, or None."""
    try:
        response = make_api_request("POST", url, json_body=body)
    except requests.HTTPError as exc:
        if exc.response is None:
            return None
        return _CORE_HTTP_ERRORS.get(exc.response.status_code)
    except requests.RequestException:
        return None
    try:
        status = response.json().get("status")
    except (ValueError, AttributeError):
        return None
    return status if isinstance(status, str) else None


def pam_authenticate(username: str, password: str) -> str | None:
    """Authenticate via core; returns a core status string or None on failure."""
    return _core_status(CORE_PAM_URL, {"username": username, "password": password})


def pam_change_password(
    username: str, current_password: str, new_password: str
) -> str | None:
    """Change an expired password via core; returns a status string or None."""
    return _core_status(
        CORE_PAM_CHANGE_URL,
        {
            "username": username,
            "current_password": current_password,
            "new_password": new_password,
        },
    )


def _throttle_keys(username: str) -> list[str]:
    """The client IP key, then the username key (if any)."""
    keys = [f"ip:{request.remote_addr}"]
    if username:
        keys.append(f"user:{username}")
    return keys


def _throttle_wait(keys: list[str]) -> int:
    """Seconds until this client may try again (0 = now).

    The username key only applies once the client's own IP has failed
    recently. Otherwise anyone hammering ``wlanpi`` would lock the admin's
    browser out too; guessing spread across many IPs is still throttled after
    each IP's first miss.
    """
    now = boot_clock()
    failures = _state()["failures"]
    ip_count, ip_last = failures.get(keys[0], (0, 0.0))
    active = keys if ip_count and now - ip_last <= FORGET_AFTER else keys[:1]
    wait = 0.0
    for key in active:
        count, last = failures.get(key, (0, 0.0))
        if count < FREE_ATTEMPTS or now - last > FORGET_AFTER:
            continue
        delay = min(MAX_DELAY, 2 ** (count - FREE_ATTEMPTS))
        wait = max(wait, last + delay - now)
    return min(MAX_DELAY, int(wait + 0.999))


def _record_failure(keys: list[str], username: str) -> None:
    now = boot_clock()
    state = _state()
    failures = state["failures"]
    with state["lock"]:
        for key in keys:
            count, last = failures.get(key, (0, 0.0))
            if now - last > FORGET_AFTER:
                count = 0
            failures[key] = (count + 1, now)
        if len(failures) > MAX_TRACKED:
            for key in [k for k, (_, t) in failures.items() if now - t > FORGET_AFTER]:
                del failures[key]
            while len(failures) > MAX_TRACKED:
                del failures[min(failures, key=lambda k: failures[k][1])]
    current_app.logger.warning(
        "failed login for %r from %s", username, request.remote_addr
    )


def _clear_failures(keys: list[str]) -> None:
    state = _state()
    with state["lock"]:
        for key in keys:
            state["failures"].pop(key, None)


def _throttled_message(wait: int) -> str:
    return f"Too many failed attempts. Try again in {wait} seconds."


def _login_session(username: str) -> None:
    """Start a fresh session and register it server-side."""
    session.clear()
    sid = secrets.token_urlsafe(32)
    now = boot_clock()
    with _update_sessions() as sessions:
        sessions[sid] = {"user": username, "created": now}
    session["sid"] = sid
    session["user"] = username
    session["csrf_token"] = secrets.token_urlsafe(32)
    session["boot_id"] = read_boot_id()
    session["last_seen"] = now
    session.permanent = True


def _revoke_user_sessions(username: str) -> None:
    with _update_sessions() as sessions:
        for sid in [s for s, rec in sessions.items() if rec.get("user") == username]:
            del sessions[sid]


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not validate_csrf():
            abort(400)
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        keys = _throttle_keys(username)
        wait = _throttle_wait(keys)
        if wait:
            return _render_login(_throttled_message(wait), 429)
        # Control characters never name an account (PAM would cut at a NUL).
        status = (
            pam_authenticate(username, password)
            if username.isprintable()
            else "failure"
        )
        if status == "success":
            _clear_failures(keys)
            _login_session(username)
            return redirect("/")
        if status == "password_change_required":
            # Carried in the signed session, not the URL, so it stays out of
            # access logs and browser history.
            session["pending_password_change"] = username
            return redirect(url_for("auth.change_password"))
        if status in _FAILED_GUESS or status not in MESSAGES:
            _record_failure(keys, username)
        return _render_login(MESSAGES.get(status, MESSAGES["failure"]), 401)
    if session.get("user"):
        return redirect("/")
    expired = request.args.get("reason") == "expired"
    return render_template("login.html", expired=expired, hostname=get_hostname())


def _render_login(error: str, code: int):
    return render_template("login.html", error=error, hostname=get_hostname()), code


@bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        if not validate_csrf():
            abort(400)
        username = request.form.get("username", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("new_password_confirm", "")
        keys = _throttle_keys(username)
        wait = _throttle_wait(keys)
        if wait:
            return _render_change(_throttled_message(wait), username, 429)
        if new_password != confirm_password:
            error = "New passwords do not match."
        elif new_password == current_password:
            error = "New password must be different from the current password."
        else:
            status = (
                pam_change_password(username, current_password, new_password)
                if username.isprintable()
                else "failure"
            )
            if status == "success":
                _clear_failures(keys)
                _revoke_user_sessions(username)
                _login_session(username)
                return redirect("/")
            if status in _FAILED_GUESS or status not in MESSAGES:
                _record_failure(keys, username)
            if status == "failure" or status not in MESSAGES:
                error = (
                    "Unable to change password. Check your current password "
                    "and try again."
                )
            else:
                error = MESSAGES[status]
        return _render_change(error, username, 400)
    return render_template(
        "change_password.html", username=session.get("pending_password_change", "")
    )


def _render_change(error: str, username: str, code: int):
    return (
        render_template("change_password.html", error=error, username=username),
        code,
    )


@bp.route("/logout", methods=["POST"])
def logout():
    if not validate_csrf():
        abort(400)
    end_session()
    return redirect(url_for("auth.login"))


@bp.route("/auth/check")
def auth_check():
    """Session check for nginx ``auth_request`` subrequests."""
    if session.get("user"):
        return "", 200
    return "", 401
