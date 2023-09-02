import subprocess

import requests
from flask import current_app, redirect, request


def service_down(service: str):
    return f"{service.capitalize()} service is unavailable or down."


def systemd_service_status(service):
    """
    Checks the status of the systemd service.
    Returns true if systemd service is running, false otherwise.
    """
    try:
        # this cmd fails if service not installed
        cmd = f"/bin/systemctl is-active --quiet {service}"
        current_app.logger.debug("subprocess is running %s" % cmd)
        subprocess.run(cmd, shell=True).check_returncode()
    except:
        # cmd failed, so systemd service not installed
        return False

    return True


def systemd_service_message(service):
    """
    Checks if systemd service is running.
    Returns '<service> is running' if it is, and '<service> is not running' if not.
    """
    status = systemd_service_status(service)
    if status:
        return f"{service} is running"
    else:
        return f"{service} is not running"


def start_stop_service(task, service):
    """
    Starts or stops a service using wlanpi-core.
    """
    headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
    }
    params = {
        "name": f"{service}",
    }
    if task == "start":
        current_app.logger.info("starting %s" % service)
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
        current_app.logger.info("stopping %s" % service)
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
