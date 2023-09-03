from flask import current_app, redirect, render_template, request

from wlanpi_webui.grafana import bp
from wlanpi_webui.utils import (service_down, start_stop_service,
                                systemd_service_status)


@bp.route("/grafana_url")
def grafana_url():
    base = request.host.split(":")[0]
    return redirect(f"http://{base}/app/grafana", code=302)


@bp.route("/grafana")
def grafana():
    base = request.host.split(":")[0]
    status = systemd_service_status("grafana-server")
    current_app.logger.debug("systemctl is-active for grafana-server is %s" % status)
    iframe = f'<iframe class="uk-cover" style="pointer-events: all;" src="https://{base}/app/grafana" height="100%" width="100%"></iframe>'
    unavailable = service_down("grafana-server")
    if status:
        return render_template("/public/iframe.html", iframe=iframe)
    else:
        return render_template("/public/service.html", service=unavailable)


@bp.route("/<task>grafana")
def start_stop_grafana(task):
    return start_stop_service(task, "grafana-server")
