from flask import render_template, request

from wlanpi_webui.cockpit import bp


@bp.route("/admin")
def cockpit():
    base = request.host.split(":")[0]
    return render_template("/public/iframe.html", iframe=f"https://{base}/app/cockpit")
