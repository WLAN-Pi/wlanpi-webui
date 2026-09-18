"""Debug page: toast tests, theme toggle and session details."""

from time import time

from flask import render_template, request, session

from wlanpi_webui.config import Config
from wlanpi_webui.debug import bp
from wlanpi_webui.utils import is_htmx

TOAST_STATUSES = ["primary", "success", "warning", "danger"]


@bp.route("/debug")
def debug():
    """Render the debug page (toast tests, theme toggle, session details)."""
    last_seen = session.get("last_seen")
    resp_data = {
        "toast_statuses": TOAST_STATUSES,
        "webui_version": Config.WEBUI_VERSION,
        "wlanpi_version": Config.WLANPI_VERSION,
        "idle_timeout": Config.IDLE_TIMEOUT,
        "boot_id": session.get("boot_id"),
        "last_seen_age": (int(time() - last_seen) if last_seen else None),
    }
    if is_htmx(request):
        return render_template("/partials/debug.html", **resp_data)
    return render_template("/extends/debug.html", **resp_data)
