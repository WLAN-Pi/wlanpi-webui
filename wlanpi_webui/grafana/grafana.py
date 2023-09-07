import ssl
import urllib

from flask import current_app, redirect, render_template, request

from wlanpi_webui.grafana import bp
from wlanpi_webui.utils import (get_apt_package_version, service_down,
                                start_stop_service, systemd_service_status)


def try_url(url):
    try:
        context = ssl._create_unverified_context()
        res = urllib.request.urlopen(url, context=context, timeout=1)
    except urllib.error.HTTPError as e:
        if e.code == 502:
            return 502
    return 0


@bp.route("/grafana_url")
def grafana_url():
    base = request.host.split(":")[0]
    return redirect(f"http://{base}/app/grafana", code=302)


@bp.route("/grafana")
def grafana():
    base = request.host.split(":")[0]

    resp_data = {"iframe_url": f"https://{base}/app/grafana"}
    status = systemd_service_status("grafana-server")
    current_app.logger.debug("systemctl is-active for grafana-server is %s" % status)
    unavailable = service_down("grafana-server")
    return_code = try_url(resp_data["iframe_url"])
    version = get_apt_package_version("grafana")
    if version == "":
        return render_template(
            "/public/service.html",
            service="Grafana does not appear to be installed.",
        )
    if return_code == 502:
        return render_template(
            "/public/service.html",
            service="Grafana URL responded with HTTP code 502. Start the service, wait a few moments, and try again.",
        )
    if status:
        return render_template("/public/partial_iframe.html", **resp_data)
    else:
        return render_template("/public/partial_service.html", service=unavailable)


@bp.route("/<task>grafana")
def start_stop_grafana(task):
    return start_stop_service(task, "grafana-server")


@bp.route("/<task>grafanascanner")
def start_stop_grafana_scanner(task):
    return start_stop_service(task, "wlanpi-grafana-scanner")
