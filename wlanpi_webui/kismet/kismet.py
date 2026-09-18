from flask import redirect, request

from wlanpi_webui.auth.auth import csrf_required
from wlanpi_webui.kismet import bp
from wlanpi_webui.utils import (
    is_htmx,
    start_stop_service,
    system_service_running_state,
    wlanpi_core_warning,
)


@bp.route("/kismet")
def kismet():
    base = request.host.split(":")[0]
    return redirect(f"http://{base}:2501", code=302)


@bp.route("/<task>kismet", methods=["POST"])
@csrf_required
def start_stop_kismet(task):
    if is_htmx(request):
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            return start_stop_service(task, "kismet")
        else:
            return wlanpi_core_warning
    return "", 204
