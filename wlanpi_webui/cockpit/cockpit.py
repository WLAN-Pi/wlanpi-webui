from flask import redirect

from wlanpi_webui.auth.auth import csrf_required
from wlanpi_webui.cockpit import bp
from wlanpi_webui.utils import start_stop_service


@bp.route("/cockpit")
def cockpit():
    return redirect("/app/cockpit")


@bp.route("/<task>cockpit", methods=["POST"])
@csrf_required
def start_stop_cockpit(task):
    return start_stop_service(task, "cockpit")
