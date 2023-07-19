from flask import current_app, render_template, request

from wlanpi_webui.grafana import bp

@bp.route("/grafana")
def grafana():
    GRAFANA_PORT = "3000"
    base = request.host.split(":")[0]
    #return redirect(f"http://{base}:{KISMET_PORT}")
    return render_template('/public/kismet.html', iframe=f"http://{base}:{GRAFANA_PORT}")
