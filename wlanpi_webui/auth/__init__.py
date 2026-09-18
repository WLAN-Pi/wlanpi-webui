#!/usr/bin/python3

"""wlanpi_webui.auth: PAM-backed session login and CSRF helpers."""

from flask import Blueprint

bp = Blueprint("auth", __name__)

from wlanpi_webui.auth import auth  # noqa: F401
