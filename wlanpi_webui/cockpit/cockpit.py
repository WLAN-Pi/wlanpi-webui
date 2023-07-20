from flask import render_template, request

from wlanpi_webui.cockpit import bp


@bp.route("/admin")
def cockpit():
    base = request.host.split(":")[0]
    return render_template("/public/kismet.html", iframe=f"http://{base}/app/admin")
