from flask import current_app, render_template, request

from wlanpi_webui.grafana import bp
from wlanpi_webui.utils import service_down, systemd_service_status


@bp.route("/grafana")
def grafana():
    base = request.host.split(":")[0]
    current_app.logger.info(
        f'systemd_service_status: {systemd_service_status("grafana")}'
    )
    status = systemd_service_status("grafana")
    iframe = f'<iframe class="uk-cover" style="pointer-events: all;" src="https://{base}/app/grafana" height="100%" width="100%"></iframe>'
    unavailable = service_down("grafana")
    if status:
        return render_template("/public/iframe.html", iframe=iframe)
    else:
        return render_template("/public/service.html", service=unavailable)
