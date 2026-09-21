from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import abort, current_app, render_template, request, send_file
from werkzeug.utils import safe_join

from wlanpi_webui.auth.auth import csrf_required, service_toggle_anchor
from wlanpi_webui.profiler import bp
from wlanpi_webui.utils import (
    is_htmx,
    start_stop_service,
    system_service_running_state,
)

getting_started = """
<details class="disclosure">
<summary>Getting started</summary>
<div class="uk-margin-small-top">
<p>Profiling a client:</p>
<ul class="uk-list uk-list-hyphen">
<li>For BYOD or custom-build WLAN Pi devices, confirm the adapter supports monitor mode and packet injection. AP mode, the default, also needs simultaneous AP and monitor support.</li>
<li>Tap <kbd>Start</kbd> above to run the profiler. The front panel menu (<kbd>Menu &gt; Apps &gt; Profiler &gt; Start</kbd>) and the CLI (<kbd>profiler -h</kbd>) work too.</li>
<li>On start, a soft AP broadcasts. The default SSID is <kbd>Profiler xxx</kbd>, where <kbd>xxx</kbd> is the last 3 characters of the eth0 MAC address. The live session above shows the SSID, passphrase, and channel.</li>
<li>Connect your client to that SSID with the passphrase shown above (default <kbd>profiler</kbd>), or scan the QR code shown there. The passphrase must match: in AP mode, the client must complete the WPA3-SAE handshake before it sends the association request we capture.</li>
<li>The client associates but has no internet access, so the connection drops. That is expected. In legacy FakeAP mode, the client does not connect at all, but the association request is still captured.</li>
</ul>
<p>The session counters and the client table below update live as clients are profiled.</p>
</div>
</details>
"""

BAND_LABELS = {"2": "2.4 GHz", "5": "5 GHz", "6": "6 GHz"}


@dataclass(frozen=True)
class Column:
    """A single column in the client capabilities table."""

    key: str
    label: str
    group: str
    kind: str = "bool"  # bool | number | raw | text
    source: str = "feature"  # feature | profile


IDENTITY_COLUMNS: tuple[Column, ...] = (
    Column("mac", "Client MAC", "Identity", "text", "profile"),
    Column("band_label", "Band", "Identity", "text", "profile"),
    Column("channel", "Channel", "Identity", "number", "profile"),
    Column("chipset", "Chipset", "Identity", "text", "profile"),
    Column("manuf", "OUI", "Identity", "text", "profile"),
    Column("is_laa", "LAA", "Identity", "bool", "profile"),
    Column("ssid", "SSID", "Identity", "text", "profile"),
    Column("bssid", "BSSID", "Identity", "text", "profile"),
    Column("capture_source", "Source", "Identity", "text", "profile"),
    Column("modifytime", "Profiled", "Identity", "text", "profile"),
)

FEATURE_COLUMNS: tuple[Column, ...] = (
    # Wi-Fi 7 (802.11be)
    Column("dot11be", "11be", "Wi-Fi 7 (be)"),
    Column("dot11be_mcs", "11be MCS", "Wi-Fi 7 (be)", "text"),
    Column("dot11be_nss", "11be NSS", "Wi-Fi 7 (be)", "number"),
    Column("dot11be_320mhz", "11be 320MHz", "Wi-Fi 7 (be)"),
    Column("dot11be_mle", "11be MLE", "Wi-Fi 7 (be)"),
    Column("dot11be_mle_mlc_type", "11be MLC Type", "Wi-Fi 7 (be)", "number"),
    Column("dot11be_mle_emlsr_support", "11be EMLSR", "Wi-Fi 7 (be)"),
    Column(
        "dot11be_mle_emlsr_padding_delay", "11be EMLSR Pad", "Wi-Fi 7 (be)", "number"
    ),
    Column(
        "dot11be_mle_emlsr_transition_delay",
        "11be EMLSR Trans",
        "Wi-Fi 7 (be)",
        "number",
    ),
    Column("dot11be_mle_emlmr_support", "11be EMLMR", "Wi-Fi 7 (be)"),
    Column(
        "dot11be_mle_max_simultaneous_links",
        "11be Max Links",
        "Wi-Fi 7 (be)",
        "number",
    ),
    Column("dot11be_mle_t2lm_negotiation_support", "11be T2LM", "Wi-Fi 7 (be)"),
    Column("dot11be_mle_link_reconfig_support", "11be Link Reconfig", "Wi-Fi 7 (be)"),
    Column("dot11be_epcs_support", "11be EPCS", "Wi-Fi 7 (be)"),
    Column("dot11be_om_support", "11be OM", "Wi-Fi 7 (be)"),
    Column("dot11be_rtwt_support", "11be R-TWT", "Wi-Fi 7 (be)"),
    Column("dot11be_mcs14_support", "11be MCS14", "Wi-Fi 7 (be)"),
    Column("dot11be_mcs15_support", "11be MCS15", "Wi-Fi 7 (be)"),
    Column("dot11aa_scs_support", "SCS", "Wi-Fi 7 (be)"),
    Column("qos_r1_mscs_support", "Mirrored SCS", "Wi-Fi 7 (be)"),
    Column(
        "dot11be_scs_traffic_description_support", "SCS Traffic Desc", "Wi-Fi 7 (be)"
    ),
    # Wi-Fi 6 / 6E (802.11ax)
    Column("dot11ax", "11ax", "Wi-Fi 6/6E (ax)"),
    Column("dot11ax_mcs", "11ax MCS", "Wi-Fi 6/6E (ax)", "text"),
    Column("dot11ax_nss", "11ax NSS", "Wi-Fi 6/6E (ax)", "number"),
    Column("dot11ax_160_mhz", "11ax 160MHz", "Wi-Fi 6/6E (ax)"),
    Column("dot11ax_six_ghz", "11ax 6GHz", "Wi-Fi 6/6E (ax)"),
    Column("dot11ax_twt", "11ax TWT", "Wi-Fi 6/6E (ax)"),
    Column("dot11ax_bsr", "11ax BSR", "Wi-Fi 6/6E (ax)"),
    Column("dot11ax_spatial_reuse", "11ax Spatial Reuse", "Wi-Fi 6/6E (ax)", "number"),
    Column("dot11ax_punctured_preamble", "11ax Punctured", "Wi-Fi 6/6E (ax)"),
    Column("dot11ax_he_su_beamformee", "11ax HE SU BF", "Wi-Fi 6/6E (ax)"),
    Column("dot11ax_he_beamformee_sts", "11ax HE BF STS", "Wi-Fi 6/6E (ax)", "number"),
    Column(
        "dot11ax_6ghz_sm_power_save", "11ax 6GHz SM PS", "Wi-Fi 6/6E (ax)", "number"
    ),
    Column("dot11ax_he_er_su_ppdu", "11ax HE ER SU", "Wi-Fi 6/6E (ax)"),
    # Wi-Fi 5 (802.11ac)
    Column("dot11ac", "11ac", "Wi-Fi 5 (ac)"),
    Column("dot11ac_mcs", "11ac MCS", "Wi-Fi 5 (ac)", "text"),
    Column("dot11ac_nss", "11ac NSS", "Wi-Fi 5 (ac)", "number"),
    Column("dot11ac_160_mhz", "11ac 160MHz", "Wi-Fi 5 (ac)"),
    Column("dot11ac_su_bf", "11ac SU BF", "Wi-Fi 5 (ac)"),
    Column("dot11ac_mu_bf", "11ac MU BF", "Wi-Fi 5 (ac)"),
    Column("dot11ac_bf_sts", "11ac BF STS", "Wi-Fi 5 (ac)", "number"),
    # Legacy
    Column("dot11n", "11n", "Legacy"),
    Column("dot11n_nss", "11n NSS", "Legacy", "number"),
    # Security
    Column("rsnx_sae_h2e", "H2E", "Security"),
    Column("gcmp256", "GCMP-256", "Security"),
    Column("dot11w", "802.11w", "Security"),
    # Roaming
    Column("dot11r", "802.11r", "Roaming"),
    Column("dot11k", "802.11k", "Roaming"),
    Column("dot11v", "802.11v", "Roaming"),
    # RF
    Column("num_channels", "Channels", "RF", "number"),
    Column("max_power", "Max Power (dBm)", "RF", "raw"),
    Column("min_power", "Min Power (dBm)", "RF", "raw"),
)

COLUMNS: tuple[Column, ...] = IDENTITY_COLUMNS + FEATURE_COLUMNS
COLUMNS_BY_KEY: dict[str, Column] = {column.key: column for column in COLUMNS}

# Prototype default visible set (the rest are available via the column picker).
DEFAULT_COLUMNS: tuple[str, ...] = (
    "mac",
    "band_label",
    "chipset",
    "manuf",
    "is_laa",
    "dot11r",
    "dot11k",
    "dot11v",
    "dot11w",
    "gcmp256",
    "rsnx_sae_h2e",
    "dot11be",
    "dot11be_mcs",
    "dot11be_nss",
    "dot11be_320mhz",
    "dot11be_mle",
    "dot11be_mle_emlsr_support",
    "dot11be_mle_emlmr_support",
    "dot11be_mle_max_simultaneous_links",
    "dot11be_epcs_support",
    "dot11be_mcs14_support",
    "dot11be_mcs15_support",
    "dot11be_rtwt_support",
    "dot11aa_scs_support",
    "qos_r1_mscs_support",
    "dot11be_scs_traffic_description_support",
)

SUMMARY_ITEMS: tuple[tuple[str, str], ...] = (
    ("dot11be", "Wi-Fi 7 (11be)"),
    ("dot11ax", "Wi-Fi 6/6E (11ax)"),
    ("dot11ac", "Wi-Fi 5 (11ac)"),
    ("dot11be_320mhz", "320 MHz"),
    ("dot11be_mle", "MLE"),
    ("dot11be_mle_emlsr_support", "EMLSR"),
    ("dot11be_mle_emlmr_support", "EMLMR"),
    ("dot11be_epcs_support", "EPCS"),
    ("dot11be_mcs14_support", "MCS14"),
    ("dot11be_mcs15_support", "MCS15"),
    ("dot11be_rtwt_support", "R-TWT"),
    ("dot11aa_scs_support", "SCS"),
    ("qos_r1_mscs_support", "Mirrored SCS"),
    ("dot11be_scs_traffic_description_support", "SCS Traffic Desc"),
    ("rsnx_sae_h2e", "H2E"),
    ("dot11w", "802.11w"),
    ("gcmp256", "GCMP-256"),
    ("dot11r", "802.11r"),
    ("dot11k", "802.11k"),
    ("dot11v", "802.11v"),
)


@dataclass
class ClientProfile:
    """A single profiled client (one row per client MAC + band)."""

    key: str
    mac: str
    band: str
    band_label: str
    channel: Any
    chipset: str
    manuf: str
    is_laa: bool
    ssid: str
    bssid: str
    capture_source: str
    profiler_version: str
    schema_version: int
    modifytime: str
    features: dict[str, Any]
    pcapng: str
    text_path: str | None
    pcap_path: str | None
    text_href: str | None
    pcap_href: str | None


def _href(path: str) -> str:
    """Map an absolute profiler file path to a WebUI download URL."""
    rel = os.path.relpath(path, current_app.config["FILES_ROOT_DIR"])
    return "/" + rel.replace(os.sep, "/")


def _band_label(band: Any) -> str:
    return BAND_LABELS.get(str(band), "Unknown")


def get_client_profiles() -> list[ClientProfile]:
    """Parse every per-client profiler JSON report into a ClientProfile."""
    root = current_app.config["PROFILER_DIR"]
    profiles: list[ClientProfile] = []
    for json_path in glob.glob(f"{root}clients/**/*.json", recursive=True):
        try:
            with open(json_path) as json_file:
                data = json.load(json_file)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        base = os.path.splitext(json_path)[0]
        text_path = f"{base}.txt"
        pcap_path = f"{base}.pcap"
        band = data.get("capture_band", "")
        try:
            modifytime = datetime.fromtimestamp(os.path.getmtime(json_path)).strftime(
                "%Y-%m-%d %H:%M:%S%z"
            )
        except OSError:
            modifytime = ""
        profiles.append(
            ClientProfile(
                key=Path(json_path).stem,
                mac=str(data.get("mac") or ""),
                band=str(band),
                band_label=_band_label(band),
                channel=data.get("capture_channel"),
                chipset=str(data.get("chipset") or "Unknown"),
                manuf=str(data.get("manuf") or "Unknown"),
                is_laa=bool(data.get("is_laa")),
                ssid=str(data.get("capture_ssid") or ""),
                bssid=str(data.get("capture_bssid") or ""),
                capture_source=str(data.get("capture_source") or ""),
                profiler_version=str(data.get("profiler_version") or ""),
                schema_version=int(data.get("schema_version") or 0),
                modifytime=modifytime,
                features=data.get("features") or {},
                pcapng=str(data.get("pcapng") or ""),
                text_path=text_path if os.path.isfile(text_path) else None,
                pcap_path=pcap_path if os.path.isfile(pcap_path) else None,
                text_href=_href(text_path) if os.path.isfile(text_path) else None,
                pcap_href=_href(pcap_path) if os.path.isfile(pcap_path) else None,
            )
        )
    profiles.sort(key=lambda profile: profile.modifytime, reverse=True)
    return profiles


def _format_value(value: Any, kind: str) -> tuple[str, str]:
    """Return (display text, css class) for a capability value."""
    if kind == "text":
        return ("" if value in (None, "") else str(value), "")
    if value is None:
        return ("N/A", "cap-na")
    if kind == "raw":
        return (str(value), "cap-num")
    if kind == "number":
        return ("N/A", "cap-na") if value == -1 else (str(value), "cap-num")
    # bool
    if value == -1:
        return ("N/A", "cap-na")
    if value in (1, True):
        return ("Yes", "cap-yes")
    if value in (0, False):
        return ("No", "cap-no")
    return (str(value), "cap-num")


def format_cell(profile: ClientProfile, column: Column) -> tuple[str, str]:
    """Return (text, css class) for one cell of the capabilities table."""
    if column.source == "profile":
        value = getattr(profile, column.key, None)
    else:
        value = profile.features.get(column.key)
    return _format_value(value, column.kind)


def build_summary(profiles: list[ClientProfile]) -> dict[str, Any]:
    """Feature/support counts for the summary block."""

    def count(key: str) -> int:
        return sum(1 for profile in profiles if profile.features.get(key) == 1)

    return {
        "total": len(profiles),
        "laa": sum(1 for profile in profiles if profile.is_laa),
        "chipsets": sorted({p.chipset for p in profiles if p.chipset}),
        "bands": sorted({p.band_label for p in profiles if p.band_label}),
        "counts": [(label, count(key)) for key, label in SUMMARY_ITEMS],
    }


def _sort_value(profile: ClientProfile, column: Column) -> tuple[int, float, str]:
    if column.source == "profile":
        value = getattr(profile, column.key, None)
    else:
        value = profile.features.get(column.key)
    if value is None or value == -1:
        return (1, 0.0, "")
    if isinstance(value, bool):
        return (0, float(value), "")
    if isinstance(value, (int, float)):
        return (0, float(value), "")
    return (0, 0.0, str(value).lower())


def sort_profiles(
    profiles: list[ClientProfile], column: Column, direction: str
) -> list[ClientProfile]:
    return sorted(
        profiles,
        key=lambda profile: _sort_value(profile, column),
        reverse=(direction == "desc"),
    )


def get_profile(stub: str) -> ClientProfile | None:
    return next(
        (profile for profile in get_client_profiles() if profile.key == stub), None
    )


def _read_json(path: str) -> dict[str, Any] | None:
    """Read a JSON object, returning None if missing or malformed."""
    try:
        with open(path) as json_file:
            data = json.load(json_file)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _humanize_seconds(value: Any) -> str:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return ""
    if seconds < 0:
        return ""
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _format_timestamp(value: Any) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _qr_escape(value: str) -> str:
    """Escape the characters that are reserved in a Wi-Fi QR payload."""
    return "".join(f"\\{ch}" if ch in '\\;,:"' else ch for ch in value)


def get_profiler_session() -> dict[str, Any]:
    """Live profiler session from the runtime files, else the last session."""
    status = _read_json(current_app.config["PROFILER_STATUS_PATH"]) or {}
    info = _read_json(current_app.config["PROFILER_INFO_PATH"]) or {}
    state = str(status.get("state") or "").lower()
    if state in ("running", "starting") and info:
        interfaces = info.get("interfaces") or {}
        ssid = str(info.get("ssid") or "")
        passphrase = str(info.get("passphrase") or "")
        wifi_qr = (
            f"WIFI:S:{_qr_escape(ssid)};T:WPA;P:{_qr_escape(passphrase)};;"
            if ssid
            else ""
        )
        return {
            "live": True,
            "state": state,
            "state_class": "is-on" if state == "running" else "is-warn",
            "profiler_version": str(info.get("profiler_version") or ""),
            "mode": str(info.get("mode") or ""),
            "phy": str(info.get("phy") or ""),
            "ap_interface": str(interfaces.get("ap") or ""),
            "monitor_interface": str(interfaces.get("monitor") or ""),
            "channel": info.get("channel"),
            "frequency": info.get("frequency"),
            "country_code": str(info.get("country_code") or ""),
            "ssid": ssid,
            "passphrase": passphrase,
            "bssid": str(info.get("bssid") or ""),
            "started_at": _format_timestamp(info.get("started_at")),
            "uptime": _humanize_seconds(info.get("uptime_seconds")),
            "profile_count": info.get("profile_count", 0),
            "failed_profile_count": info.get("failed_profile_count", 0),
            "total_clients_seen": info.get("total_clients_seen", 0),
            "invalid_frame_count": info.get("invalid_frame_count", 0),
            "bad_fcs_count": info.get("bad_fcs_count", 0),
            "last_profile": str(info.get("last_profile") or ""),
            "last_profile_timestamp": _format_timestamp(
                info.get("last_profile_timestamp")
            ),
            "wifi_qr": wifi_qr,
        }
    last = _read_json(current_app.config["PROFILER_LAST_SESSION_PATH"]) or {}
    session = last.get("session") or {}
    exit_info = last.get("exit") or {}
    configuration = last.get("configuration") or {}
    metrics = last.get("metrics") or {}
    exit_status = str(exit_info.get("status") or "")
    return {
        "live": False,
        "state": state or "stopped",
        "state_class": "is-bad"
        if exit_status in ("failed", "interrupted")
        else "is-off",
        "has_last_session": bool(last),
        "wifi_qr": "",
        "last": {
            "status": exit_status,
            "reason": str(exit_info.get("reason") or ""),
            "message": str(exit_info.get("message") or ""),
            "started_at": _format_timestamp(session.get("started_at")),
            "ended_at": _format_timestamp(session.get("ended_at")),
            "duration": _humanize_seconds(session.get("duration_seconds")),
            "mode": str(configuration.get("mode") or ""),
            "channel": configuration.get("channel"),
            "frequency": configuration.get("frequency"),
            "ssid": str(configuration.get("ssid") or ""),
            "profile_count": metrics.get("profile_count", 0),
            "failed_profile_count": metrics.get("failed_profile_count", 0),
            "total_clients_seen": metrics.get("total_clients_seen", 0),
            "last_profile": str(metrics.get("last_profile") or ""),
        },
    }


def profiler_service_view(session: dict[str, Any], running: bool) -> dict[str, str]:
    """Badge and message for the profiler service bar.

    "Up" comes from the profiler's own status file. The systemd state covers
    the window between the unit starting and the profiler writing that file,
    which is what keeps the bar from regressing to "stopped" on the next poll.
    """
    if session.get("live") and session.get("state") == "running":
        return {
            "state_class": "is-on",
            "state_label": "Running",
            "message": "Profiler is up and ready to capture association requests.",
        }
    if session.get("state") == "starting" or running:
        return {
            "state_class": "is-warn",
            "state_label": "Starting",
            "message": "Profiler is starting...",
        }
    return {
        "state_class": "is-off",
        "state_label": "Stopped",
        "message": "Start the profiler to begin capturing.",
    }


def get_reports() -> list[dict[str, str]]:
    """Session-level CSV reports."""
    root = current_app.config["PROFILER_DIR"]
    reports = []
    for path in glob.glob(f"{root}reports/*.csv"):
        try:
            modifytime = datetime.fromtimestamp(os.path.getmtime(path)).strftime(
                "%Y-%m-%d %H:%M:%S%z"
            )
        except OSError:
            modifytime = ""
        reports.append(
            {
                "name": Path(path).stem.replace("profiler-", ""),
                "modifytime": modifytime,
                "href": _href(path),
            }
        )
    reports.sort(key=lambda report: report["modifytime"], reverse=True)
    return reports


def get_profiler_files_to_purge() -> list:
    """Provide a purge list for all profiler files"""
    files = []
    _glob = glob.glob(f"{current_app.config['PROFILER_DIR']}**", recursive=True)
    for _file in _glob:
        if not os.path.isdir(_file):
            if os.path.isfile(_file):
                if any(x in _file for x in [".pcap", ".pcapng"]):
                    files.append(_file)
                if any(x in _file for x in [".txt"]):
                    files.append(_file)
                if ".csv" in _file:
                    files.append(_file)
                if ".json" in _file:
                    files.append(_file)
    return files


@bp.route("/profiler/purge")
def purge():
    """Purges profiler files"""
    files = get_profiler_files_to_purge()
    inner = "\r\n".join([f"rm {file}" for file in files])
    content = f"""<div>
<p>The <tt>webui</tt> process does not have permission to remove files.</p>
<p>To purge profiler files, open a root shell and paste in the following:<br /><pre>{inner}</pre></p>
</div>"""
    if not files:
        content = '<div class="uk-alert-danger" uk-alert><p>No profiler files found on host to generate purge script.</p></div>'
    resp_data = {"content": content, "show_capabilities": False}
    if is_htmx(request):
        return render_template("/partials/profiler.html", **resp_data)
    else:
        return render_template("/extends/profiler.html", **resp_data)


@bp.route("/profiler/profile")
def profile():
    """Render the text report for one profiled client in a modal"""
    stub = request.args.get("profile") or ""
    client = get_profile(stub)
    if client is None or client.text_path is None:
        abort(404)
    try:
        content = Path(client.text_path).read_text()
    except OSError:
        abort(404)
    if is_htmx(request):
        return render_template(
            "/partials/profiler_report_modal.html",
            stub=client.key,
            title=f"{client.mac} ({client.band_label})",
            content=content,
            download_url=client.text_href or "#",
        )
    return "", 204


@bp.route("/profiler/capabilities")
def capabilities():
    """Client capabilities summary + table (htmx partial)"""
    profiles = get_client_profiles()
    needle = (request.args.get("filter") or "").strip().lower()
    if needle:
        profiles = [
            profile
            for profile in profiles
            if needle in profile.mac.lower()
            or needle in profile.chipset.lower()
            or needle in profile.manuf.lower()
        ]
    sort_key = request.args.get("sort") or ""
    direction = request.args.get("dir") or "asc"
    if sort_key in COLUMNS_BY_KEY:
        profiles = sort_profiles(profiles, COLUMNS_BY_KEY[sort_key], direction)
    rows = [
        {
            "profile": profile,
            "cells": [format_cell(profile, column) for column in COLUMNS],
        }
        for profile in profiles
    ]
    return render_template(
        "/partials/profiler_capabilities.html",
        columns=COLUMNS,
        default_columns=DEFAULT_COLUMNS,
        rows=rows,
        summary=build_summary(profiles),
        sort=sort_key,
        direction=direction,
        filter=request.args.get("filter") or "",
    )


@bp.route("/profiler/session")
def profiler_session():
    """Live profiler session data (htmx partial)"""
    session = get_profiler_session()
    return render_template(
        "/partials/profiler_session.html",
        session=session,
        service=profiler_service_view(
            session, system_service_running_state("wlanpi-profiler", quiet=True)
        ),
    )


@bp.route("/profiler/profiles")
def profiler():
    """Profiles"""
    session = get_profiler_session()
    profiler_running = system_service_running_state("wlanpi-profiler")
    resp_data = {
        "content": "",
        "show_capabilities": True,
        "getting_started": getting_started,
        "profiler_running": profiler_running,
        "service": profiler_service_view(session, profiler_running),
        "profiler_toggle": service_toggle_anchor(
            profiler_running, "/startprofiler", "/stopprofiler"
        ),
        "profiler_qr": session.get("wifi_qr") or "",
        "profiler_ssid": session.get("ssid") or "",
        "reports": get_reports(),
    }
    if is_htmx(request):
        return render_template("/partials/profiler.html", **resp_data)
    else:
        return render_template("/extends/profiler.html", **resp_data)


@bp.route("/profiler/<path:filename>")
def get_profiler_results(filename):
    """Handle when user downloads profiler results"""
    safe_path = safe_join(current_app.config["PROFILER_DIR"], filename)
    try:
        return send_file(safe_path, as_attachment=True)
    except FileNotFoundError:
        abort(404)
    except IsADirectoryError:
        abort(405)


@bp.route("/<task>profiler", methods=["POST"])
@csrf_required
def start_stop_profiler(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-profiler")
    return "", 204
