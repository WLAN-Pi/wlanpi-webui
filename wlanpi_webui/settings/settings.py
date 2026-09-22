from flask import redirect, render_template, request, session

from wlanpi_webui.auth.auth import csrf_required
from wlanpi_webui.config import Config
from wlanpi_webui.settings import bp
from wlanpi_webui.utils import (
    get_core_json,
    get_safe_referrer_target,
    is_htmx,
    post_core_json,
    queue_toast,
)


@bp.route("/settings")
def settings():
    datetime_info = get_core_json("/api/v1/system/datetime") or {}
    tz_list = get_core_json("/api/v1/system/timezone/list") or {}
    tz_info = get_core_json("/api/v1/system/timezone") or {}
    reg = get_core_json("/api/v1/system/reg-domain") or {}
    reg_list = get_core_json("/api/v1/system/reg-domain/list") or {}
    ntp = get_core_json("/api/v1/system/ntp") or {}

    resp_data = {
        "idle_timeout": Config.IDLE_TIMEOUT,
        "boot_id": session.get("boot_id"),
        "current_datetime": (
            datetime_info.get("display")
            or datetime_info.get("datetime")
            or "unavailable"
        ),
        # /system/timezone reads systemd's authoritative value; /system/datetime's
        # timezone can lag because it prefers a stale /etc/timezone.
        "current_timezone": tz_info.get("timezone")
        or datetime_info.get("timezone")
        or "",
        "timezones": tz_list.get("timezones") or [],
        "reg_country": reg.get("country") or "unknown",
        "reg_countries": reg_list.get("countries") or [],
        "ntp_enabled": bool(ntp.get("ntp_service")),
    }
    if is_htmx(request):
        return render_template("/partials/settings.html", **resp_data)
    return render_template("/extends/settings.html", **resp_data)


@bp.route("/alerts")
def alerts():
    """Active wlanpi-core health conditions (see the context processor)."""
    if is_htmx(request):
        return render_template("/partials/alerts.html")
    return render_template("/extends/alerts.html")


@bp.route("/settings/timezone", methods=["POST"])
@csrf_required
def set_timezone():
    timezone = (request.form.get("timezone") or "").strip()
    if not timezone:
        queue_toast("Choose a timezone first.", "warning")
    elif post_core_json(
        "/api/v1/system/timezone/set", json_body={"timezone": timezone}
    ):
        queue_toast(f"Timezone set to {timezone}.", "success")
    else:
        queue_toast("Could not set the timezone.", "warning")
    return redirect(get_safe_referrer_target())


@bp.route("/settings/ntp", methods=["POST"])
@csrf_required
def set_ntp():
    enabled = (request.form.get("enabled") or "true").lower() != "false"
    if post_core_json("/api/v1/system/ntp", json_body={"enabled": enabled}):
        queue_toast(
            "Automatic time sync enabled."
            if enabled
            else "Automatic time sync disabled.",
            "success",
        )
    else:
        queue_toast("Could not change automatic time sync.", "warning")
    return redirect(get_safe_referrer_target())


@bp.route("/settings/reg-domain", methods=["POST"])
@csrf_required
def set_reg_domain():
    country = (request.form.get("country") or "").strip().upper()
    if len(country) != 2:
        queue_toast("Choose a country first.", "warning")
    elif post_core_json(
        "/api/v1/system/reg-domain/set", json_body={"country": country}
    ):
        queue_toast(f"Regulatory domain set to {country}.", "success")
    else:
        queue_toast("Could not set the regulatory domain.", "warning")
    return redirect(get_safe_referrer_target())


@bp.route("/settings/reboot", methods=["POST"])
@csrf_required
def reboot_device():
    if post_core_json("/api/v1/system/reboot"):
        queue_toast("Rebooting the WLAN Pi…", "success")
    else:
        queue_toast("Could not reboot the device.", "warning")
    return redirect(get_safe_referrer_target())


@bp.route("/settings/shutdown", methods=["POST"])
@csrf_required
def shutdown_device():
    if post_core_json("/api/v1/system/shutdown"):
        queue_toast("Shutting down the WLAN Pi…", "success")
    else:
        queue_toast("Could not shut down the device.", "warning")
    return redirect(get_safe_referrer_target())
