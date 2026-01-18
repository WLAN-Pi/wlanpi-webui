from flask import redirect, request
from flask_minify import decorators as minify_decorators

from wlanpi_webui.kismet import bp
from wlanpi_webui.utils import (
    is_htmx,
    start_stop_service,
    system_service_running_state,
    systemd_service_message,
    wlanpi_core_warning,
)


@bp.route("/kismet")
def kismet():
    base = request.host.split(":")[0]
    return redirect(f"http://{base}:2501", code=302)


@bp.route("/<task>kismet")
def start_stop_kismet(task):
    if is_htmx(request):
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            start_stop_service(task, "kismet")
        else:
            return wlanpi_core_warning
    return "", 204


@bp.route("/kismet/side_menu")
@minify_decorators.minify(html=True)
def kismet_side_menu():
    if is_htmx(request):
        kismet_message = systemd_service_message("kismet")
        kismet_status = system_service_running_state("kismet")
        if kismet_status:
            # active
            kismet_task_url = "/stopkismet"
            kismet_task_anchor_text = "STOP"
        else:
            # not active
            kismet_task_url = "/startkismet"
            kismet_task_anchor_text = "START"
        args = {
            "kismet_message": kismet_message,
            "kismet_task_url": kismet_task_url,
            "kismet_task_anchor_text": kismet_task_anchor_text,
        }
        if kismet_status:
            # active
            html = """
            <li class="uk-nav-header">{kismet_message}</li>
            <li><a hx-get="{kismet_task_url}"
                   hx-indicator=".progress">{kismet_task_anchor_text}</a></li>
            <li><a class="uk-link" href="/kismet" target="_blank">LAUNCH KISMET</a></li>
            """.format(**args)
        else:
            # not active
            html = """
            <li class="uk-nav-header">{kismet_message}</li>
            <li><a hx-get="{kismet_task_url}"
                   hx-indicator=".progress">{kismet_task_anchor_text}</li>
            """.format(**args)
        return html


@bp.route("/kismet/main_menu")
def kismet_main_menu():
    if is_htmx(request):
        kismet_message = systemd_service_message("kismet")
        kismet_status = system_service_running_state("kismet")
        if kismet_status:
            # active
            kismet_task_url = "/stopkismet"
            kismet_task_anchor_text = "STOP"
        else:
            # not active
            kismet_task_url = "/startkismet"
            kismet_task_anchor_text = "START"
        args = {
            "kismet_message": kismet_message,
            "kismet_task_url": kismet_task_url,
            "kismet_task_anchor_text": kismet_task_anchor_text,
        }
        if kismet_status:
            # active
            html = """
            <li class="uk-nav-header">{kismet_message}</li>
            <li><a hx-get="{kismet_task_url}"
                   hx-indicator=".progress">{kismet_task_anchor_text}</a></li>
            <li class="uk-nav-divider"></li>
            <li><a class="uk-link" href="/kismet" target="_blank">LAUNCH KISMET</a></li>
            """.format(**args)
        else:
            # not active
            html = """
            <li class="uk-nav-header">{kismet_message}</li>
            <li><a hx-get="{kismet_task_url}"
                   hx-indicator=".progress">{kismet_task_anchor_text}</li>
            """.format(**args)
        return html
