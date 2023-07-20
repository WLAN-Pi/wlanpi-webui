from flask import render_template, request

from wlanpi_webui.kismet import bp


@bp.route("/kismet")
def kismet():
    base = request.host.split(":")[0]
    return render_template("/public/kismet.html", iframe=f"http://{base}/app/kismet")
