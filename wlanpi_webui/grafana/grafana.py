from flask import render_template, request

from wlanpi_webui.grafana import bp


@bp.route("/grafana")
def grafana():
    base = request.host.split(":")[0]
    return render_template("/public/kismet.html", iframe=f"http://{base}/app/grafana")
