from flask import redirect

from wlanpi_webui.auth.auth import csrf_required
from wlanpi_webui.cockpit import bp
from wlanpi_webui.utils import app_url, start_stop_service


@bp.route("/cockpit")
def cockpit():
    return redirect(app_url(9090, "/app/cockpit/"))


@bp.route("/<task>cockpit", methods=["POST"])
@csrf_required
def start_stop_cockpit(task):
    return start_stop_service(task, "cockpit")
