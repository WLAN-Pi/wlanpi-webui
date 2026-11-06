from flask import render_template, request

from wlanpi_webui.apps import bp
from wlanpi_webui.auth.auth import service_toggle_anchor
from wlanpi_webui.grafana.grafana import GRAFANA_STATES, grafana_state, grafana_toggle
from wlanpi_webui.profiler.profiler import get_profiler_session, profiler_toggle
from wlanpi_webui.utils import SERVICE_STATES, is_htmx, system_service_state


@bp.route("/apps")
def apps():
    """Render the apps shell; cards lazy-load from ``/apps/cards``."""
    if is_htmx(request):
        return render_template("/partials/apps.html")
    return render_template("/extends/apps.html")


@bp.route("/apps/cards")
def apps_cards():
    """Render the app cards (service checks, may be slow)."""
    profiler = system_service_state("wlanpi-profiler")
    profiler_session = get_profiler_session(profiler)
    toggle = profiler_toggle(profiler, profiler_session)
    if profiler_session["up"] and profiler in ("stopped", "failed"):
        profiler = "running" if profiler_session["state"] == "running" else "starting"
    kismet = system_service_state("kismet")
    profiler_label, profiler_class = SERVICE_STATES[profiler]
    kismet_label, kismet_class = SERVICE_STATES[kismet]
    # systemd reports Grafana active long before it listens (about a minute
    # of migrations on first start), so use the state that probes the port.
    grafana = grafana_state()["state"]
    grafana_label, grafana_class, _ = GRAFANA_STATES[grafana]

    resp_data = {
        "profiler_running": profiler == "running",
        "profiler_state_label": profiler_label,
        "profiler_state_class": profiler_class,
        "profiler_settling": profiler in ("starting", "stopping"),
        "profiler_toggle": toggle,
        "kismet_running": kismet == "running",
        "kismet_state_label": kismet_label,
        "kismet_state_class": kismet_class,
        "kismet_settling": kismet in ("starting", "stopping"),
        "kismet_toggle": service_toggle_anchor(kismet, "/startkismet", "/stopkismet"),
        "grafana_state": grafana,
        "grafana_state_label": grafana_label,
        "grafana_state_class": grafana_class,
        "grafana_settling": grafana not in ("running", "stopped"),
        "grafana_toggle": grafana_toggle(grafana),
    }

    return render_template("/partials/apps_cards.html", **resp_data)
