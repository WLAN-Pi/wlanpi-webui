#!/usr/bin/python3

"""wlanpi_webui.auth.auth

PAM-backed session login for the WLAN Pi WebUI.

The WebUI runs unprivileged as the ``wlanpi`` user, so it cannot run the PAM
conversation itself for other users. It brokers authentication through the
root-running wlanpi-core ``/api/v1/auth/pam`` endpoints (HMAC-signed, loopback
only, added in wlanpi-core 2.1.19). Passwords are never persisted or logged.
"""

from __future__ import annotations

import hmac
import secrets

import requests
from flask import abort, redirect, render_template, request, session, url_for

from wlanpi_webui.auth import bp
from wlanpi_webui.utils import make_api_request

CORE_PAM_URL = "https://127.0.0.1:31415/api/v1/auth/pam"
CORE_PAM_CHANGE_URL = f"{CORE_PAM_URL}/change"


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
    return bool(expected and sent) and hmac.compare_digest(sent, expected)


def csrf_required(f):
    """Reject requests without a valid CSRF token."""

    def wrapper(*args, **kwargs):
        if not validate_csrf():
            abort(400, description="Missing or invalid CSRF token")
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


def hx_post_anchor(url: str, inner: str) -> str:
    """Build an htmx POST anchor carrying the CSRF token for ``url``."""
    token = get_csrf_token()
    return (
        f'<a hx-post="{url}" hx-indicator=".progress" '
        f'hx-headers=\'{{"X-CSRF-Token": "{token}"}}\'>{inner}</a>'
    )


def pam_authenticate(username: str, password: str) -> str | None:
    """Authenticate via core; returns a core status string or None on failure."""
    try:
        response = make_api_request(
            "POST", CORE_PAM_URL, json_body={"username": username, "password": password}
        )
    except requests.RequestException:
        return None
    status = response.json().get("status")
    return status if isinstance(status, str) else None


def pam_change_password(
    username: str, current_password: str, new_password: str
) -> str | None:
    """Change an expired password via core; returns a status string or None."""
    try:
        response = make_api_request(
            "POST",
            CORE_PAM_CHANGE_URL,
            json_body={
                "username": username,
                "current_password": current_password,
                "new_password": new_password,
            },
        )
    except requests.RequestException:
        return None
    status = response.json().get("status")
    return status if isinstance(status, str) else None


def _login_session(username: str):
    session.clear()
    session["user"] = username
    session["csrf_token"] = secrets.token_urlsafe(32)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not validate_csrf():
            abort(400)
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        status = pam_authenticate(username, password)
        if status == "success":
            _login_session(username)
            return redirect("/")
        if status == "password_change_required":
            return redirect(url_for("auth.change_password"))
        if status is None:
            error = "Unable to reach wlanpi-core. Is the service running?"
        else:
            error = "Incorrect username or password."
        return render_template("login.html", error=error), 401
    return render_template("login.html")


@bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        if not validate_csrf():
            abort(400)
        username = request.form.get("username", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        status = pam_change_password(username, current_password, new_password)
        if status == "success":
            _login_session(username)
            return redirect("/")
        if status is None:
            error = "Unable to reach wlanpi-core. Is the service running?"
        else:
            error = (
                "Unable to change password. Check your current password and try again."
            )
        return render_template("change_password.html", error=error), 400
    return render_template("change_password.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/auth/check")
def auth_check():
    """Session check for nginx ``auth_request`` subrequests."""
    if session.get("user"):
        return "", 200
    return "", 401
