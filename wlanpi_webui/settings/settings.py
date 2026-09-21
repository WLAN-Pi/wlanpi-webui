from flask import render_template, request, session

from wlanpi_webui.config import Config
from wlanpi_webui.settings import bp
from wlanpi_webui.utils import is_htmx


@bp.route("/settings")
def settings():
    resp_data = {
        "idle_timeout": Config.IDLE_TIMEOUT,
        "boot_id": session.get("boot_id"),
    }
    if is_htmx(request):
        return render_template("/partials/settings.html", **resp_data)
    return render_template("/extends/settings.html", **resp_data)


@bp.route("/alerts")
def alerts():
    """Active wlanpi-core health conditions (see the context processor)."""
    if is_htmx(request):
        return render_template("/partials/alerts.html")
    return render_template("/extends/alerts.html")
