import requests
from flask import current_app, redirect, request

from wlanpi_webui.kismet import bp
from wlanpi_webui.utils import systemd_service_message


@bp.route("/kismet")
def kismet():
    base = request.host.split(":")[0]
    return redirect(f"http://{base}:2501", code=302)


@bp.route("/<task>kismet")
def start_stop_kismet(task):
    headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
    }
    params = {
        "name": "kismet",
    }
    if task == "start":
        current_app.logger.info("starting kismet")
        try:
            start_url = "http://127.0.0.1:31415/api/v1/system/service/start"
            response = requests.post(
                start_url,
                params=params,
                headers=headers,
            )
            if response.status_code != 200:
                current_app.logger.info(
                    f'systemd_service_message: {systemd_service_message("wlanpi-core")}'
                )
                current_app.logger.info("%s generated %s response", start_url, response)
            return redirect(request.referrer)
        except Exception as error:
            current_app.logger.error(error)
            return redirect(request.referrer)
    elif task == "stop":
        current_app.logger.info("stopping kismet")
        try:
            stop_url = "http://127.0.0.1:31415/api/v1/system/service/stop"
            response = requests.post(
                stop_url,
                params=params,
                headers=headers,
            )
            if response.status_code != 200:
                current_app.logger.info(
                    f'systemd_service_message: {systemd_service_message("wlanpi-core")}'
                )
                current_app.logger.info("%s generated %s response", stop_url, response)
            return redirect(request.referrer)
        except Exception as error:
            current_app.logger.error(error)
            return redirect(request.referrer)
