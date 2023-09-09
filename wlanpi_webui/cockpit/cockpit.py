from flask import render_template, request

from wlanpi_webui.cockpit import bp
from wlanpi_webui.utils import is_htmx, start_stop_service


@bp.route("/cockpit")
def cockpit():
    base = request.host.split(":")[0]
    resp_data = {"iframe_url": f"https://{base}/app/cockpit"}
    if is_htmx(request):
        return render_template("/partials/iframe.html", **resp_data)
    else:
        return render_template("/extends/iframe.html", **resp_data)


@bp.route("/<task>cockpit")
def start_stop_cockpit(task):
    return start_stop_service(task, "cockpit")
