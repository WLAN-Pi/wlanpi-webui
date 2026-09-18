from flask import render_template, request

from wlanpi_webui.settings import bp
from wlanpi_webui.utils import is_htmx


@bp.route("/settings")
def settings():
    if is_htmx(request):
        return render_template("/partials/settings.html")
    return render_template("/extends/settings.html")
