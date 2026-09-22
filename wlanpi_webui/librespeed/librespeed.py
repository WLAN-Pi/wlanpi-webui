import urllib.parse

from flask import abort, jsonify, redirect, render_template, request

from wlanpi_webui.auth.auth import csrf_required
from wlanpi_webui.librespeed import bp
from wlanpi_webui.utils import (
    SPEEDTEST_NOTE_MAX,
    format_speedtest_tested_at,
    get_speedtest_result,
    is_htmx,
    load_speedtest_results,
    queue_toast,
    save_speedtest_result,
    set_speedtest_note,
)


@bp.route("/speedtest/librespeed")
def librespeed():
    return redirect("/app/librespeed/librespeed_detailed.html")


@bp.route("/speedtest/librespeed/details")
def librespeed_detailed():
    # Merged into the single speedtest page; keep old bookmarks working.
    return redirect("/speedtest/librespeed")


# The old report URLs; keep old links working.
@bp.route("/speedtest/report")
@bp.route("/speedtest/report/<path:rest>")
def old_report(rest=None):
    target = "/app/librespeed/results"
    if rest:
        target = f"{target}/{rest}"
    return redirect(target, code=301)


def _same_origin() -> bool:
    """True when the request came from this origin, not another site.

    The LibreSpeed page is a static file with no CSRF token, so the report
    endpoint leans on the session cookie (already required) plus this check and
    a JSON content type, which a cross-site form post cannot set.
    """
    site = request.headers.get("Sec-Fetch-Site")
    if site:
        return site in ("same-origin", "same-site", "none")
    origin = request.headers.get("Origin")
    if not origin:
        return True
    return urllib.parse.urlparse(origin).netloc == request.host


def _num(value) -> str:
    """Two decimals, matching the speedtest page's own formatting."""
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _result_context(result: dict | None) -> dict:
    headline = []
    latency = []
    details = []
    if result:
        # Display copy: the lede, the Details row, and the canvas all read from
        # this, so the stored UTC value never reaches the page.
        result = {
            **result,
            "tested_at": format_speedtest_tested_at(result.get("tested_at")) or "n/a",
        }
        headline = [
            ("Download (Mbps)", _num(result.get("download_mbps"))),
            ("Upload (Mbps)", _num(result.get("upload_mbps"))),
        ]
        latency = [
            (
                "Unloaded",
                _num(result.get("ping_ms")),
                _num(result.get("jitter_ms")),
            ),
            (
                "Loaded",
                _num(result.get("loaded_ping_ms")),
                _num(result.get("loaded_jitter_ms")),
            ),
        ]
        details = [
            ("Download minimum (Mbps)", _num(result.get("download_min_mbps"))),
            ("Download maximum (Mbps)", _num(result.get("download_max_mbps"))),
            ("Upload minimum (Mbps)", _num(result.get("upload_min_mbps"))),
            ("Upload maximum (Mbps)", _num(result.get("upload_max_mbps"))),
            ("Downloaded (MB)", _num(result.get("download_mb"))),
            ("Uploaded (MB)", _num(result.get("upload_mb"))),
            ("Duration (s)", _num(result.get("duration_s"))),
            ("Tested", result.get("tested_at") or "n/a"),
        ]
    return {
        "result": result,
        "headline": headline,
        "latency": latency,
        "details": details,
        "note_max": SPEEDTEST_NOTE_MAX,
    }


def _result_rows(results: list[dict]) -> list[dict]:
    """Pre-format the stored runs for the results table."""
    return [
        {
            "id": r.get("id"),
            "tested_at": format_speedtest_tested_at(r.get("tested_at")) or "n/a",
            "download": _num(r.get("download_mbps")),
            "upload": _num(r.get("upload_mbps")),
            "ping": _num(r.get("ping_ms")),
            "jitter": _num(r.get("jitter_ms")),
            "note": (r.get("note") or "").strip(),
        }
        for r in results
    ]


@bp.route("/app/librespeed/results", methods=["POST"])
def save_speedtest_report():
    """Store a speedtest result posted by the LibreSpeed page."""
    if not _same_origin():
        abort(403)
    result = save_speedtest_result(request.get_json(silent=True))
    if result is None:
        abort(400)
    queue_toast(
        f"Speedtest: {_num(result.get('download_mbps'))} Mbps down / "
        f"{_num(result.get('upload_mbps'))} Mbps up",
        "success",
    )
    return jsonify(
        {"id": result["id"], "url": f"/app/librespeed/results/{result['id']}"}
    )


@bp.route("/app/librespeed/results")
def speedtest_results():
    """Stored speedtest results, newest first."""
    resp_data = {"rows": _result_rows(load_speedtest_results())}
    if is_htmx(request):
        return render_template("/partials/speedtest_results.html", **resp_data)
    return render_template("/extends/speedtest_results.html", **resp_data)


@bp.route("/app/librespeed/results/<result_id>")
def speedtest_result(result_id):
    """One stored result, with its note."""
    result = get_speedtest_result(result_id)
    if result is None:
        abort(404)
    resp_data = _result_context(result)
    if is_htmx(request):
        return render_template("/partials/speedtest_result.html", **resp_data)
    return render_template("/extends/speedtest_result.html", **resp_data)


@bp.route("/app/librespeed/results/<result_id>/note", methods=["POST"])
@csrf_required
def speedtest_result_note(result_id):
    """Attach a short note to a result."""
    note = (request.form.get("note") or "").strip()
    if len(note) > SPEEDTEST_NOTE_MAX:
        abort(400)
    if not set_speedtest_note(result_id, note):
        abort(404)
    return redirect(f"/app/librespeed/results/{result_id}")
