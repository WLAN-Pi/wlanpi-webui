from flask import render_template, request

from wlanpi_webui.cockpit import bp
from wlanpi_webui.utils import start_stop_service


@bp.route("/cockpit")
def cockpit():
    base = request.host.split(":")[0]
    iframe = f'<iframe class="uk-cover" style="pointer-events: all;" src="https://{base}/app/cockpit" height="100%" width="100%"></iframe>'
    return render_template("/public/iframe.html", iframe=iframe)

@bp.route("/<task>cockpit")
def start_stop_cockpit(task):
    return start_stop_service(task, "cockpit")
