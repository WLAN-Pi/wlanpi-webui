from flask import jsonify, redirect, request

from wlanpi_webui.auth.auth import csrf_required
from wlanpi_webui.kismet import bp
from wlanpi_webui.utils import (
    is_htmx,
    start_stop_service,
    system_service_running_state,
)


@bp.route("/kismet/status")
def kismet_status():
    """Report whether Kismet is running so the dashboard can avoid a dead tab."""
    return jsonify({"running": system_service_running_state("kismet")})


@bp.route("/kismet")
def kismet():
    base = request.host.split(":")[0]
    return redirect(f"http://{base}:2501", code=302)


@bp.route("/<task>kismet", methods=["POST"])
@csrf_required
def start_stop_kismet(task):
    if is_htmx(request):
        return start_stop_service(task, "kismet")
    return "", 204
