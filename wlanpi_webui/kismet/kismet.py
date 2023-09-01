from flask import redirect, request

from wlanpi_webui.kismet import bp


@bp.route("/kismet")
def kismet():
    base = request.host.split(":")[0]
    proto = request.host_url.split(":")[0]
    return redirect(f"{proto}://{base}:2501", code=302)
