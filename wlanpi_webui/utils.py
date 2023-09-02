import subprocess

from flask import current_app


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
