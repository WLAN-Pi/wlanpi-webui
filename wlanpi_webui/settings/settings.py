from flask import render_template, request, session

from wlanpi_webui.config import Config
from wlanpi_webui.settings import bp
from wlanpi_webui.utils import is_htmx

TOAST_STATUSES = ["primary", "success", "warning", "danger"]


@bp.route("/settings")
def settings():
    resp_data = {
        "toast_statuses": TOAST_STATUSES,
        "idle_timeout": Config.IDLE_TIMEOUT,
        "boot_id": session.get("boot_id"),
    }
    if is_htmx(request):
        return render_template("/partials/settings.html", **resp_data)
    return render_template("/extends/settings.html", **resp_data)


@bp.route("/notifications")
def notifications():
    """Session-only record of toasts; the list is filled in by app.js."""
    if is_htmx(request):
        return render_template("/partials/notifications.html")
    return render_template("/extends/notifications.html")
