from flask import current_app, render_template, request

from wlanpi_webui.cockpit import bp
from wlanpi_webui.utils import service_down, systemd_service_status


@bp.route("/admin")
def cockpit():
    base = request.host.split(":")[0]
    current_app.logger.info(systemd_service_status("cockpit"))
    status = systemd_service_status("cockpit")
    iframe = f'<iframe class="uk-cover" style="pointer-events: all;" src="https://{base}/app/cockpit" height="100%" width="100%"></iframe>'
    unavailable = service_down("cockpit")
    if status:
        return render_template("/public/iframe.html", iframe=iframe)
    else:
        return render_template("/public/service.html", service=unavailable)
