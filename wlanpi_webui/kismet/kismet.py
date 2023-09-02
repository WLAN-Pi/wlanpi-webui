from flask import redirect, request

from wlanpi_webui.kismet import bp
from wlanpi_webui.utils import start_stop_service


@bp.route("/kismet")
def kismet():
    base = request.host.split(":")[0]
    return redirect(f"http://{base}:2501", code=302)


@bp.route("/<task>kismet")
def start_stop_kismet(task):
    return start_stop_service(task, "kismet")
