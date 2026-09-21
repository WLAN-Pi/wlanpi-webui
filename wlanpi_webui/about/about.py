from flask import abort, current_app, render_template, request, send_file

from wlanpi_webui.about import bp
from wlanpi_webui.auth.auth import csrf_required
from wlanpi_webui.utils import (
    beacon_data_path,
    is_beacon_armed,
    is_htmx,
    set_beacon_armed,
)


@bp.route("/about")
def about():
    if is_htmx(request):
        return render_template("/partials/about.html")
    else:
        return render_template("/extends/about.html")


@bp.route("/packetstorm")
def packetstorm():
    if is_htmx(request):
        return render_template("/partials/packetstorm.html")
    else:
        return render_template("/extends/packetstorm.html")


@bp.route("/beacon/arm", methods=["POST"])
@csrf_required
def beacon_arm():
    """Arm the hidden page. Idempotent, no body, no anti-cheat."""
    if not set_beacon_armed():
        return "", 500
    return "", 204


@bp.route("/beacon")
def beacon():
    # Disarmed is a 404, never a 403: a 403 would confirm something is here.
    if not is_beacon_armed():
        if is_htmx(request):
            return "", 404
        abort(404)
    # An armed device without the data gets an install note, not a 404.
    context = {
        "wad_available": beacon_data_path() is not None,
        "wad_path": current_app.config.get("BEACON_DATA_PATH"),
    }
    if is_htmx(request):
        return render_template("/partials/beacon.html", **context)
    return render_template("/extends/beacon.html", **context)


@bp.route("/beacon/data")
def beacon_data():
    """Stream the game data to the engine. Same lock as the page itself."""
    if not is_beacon_armed():
        abort(404)
    path = beacon_data_path()
    if not path:
        abort(404)
    # conditional=True gives ETag/Last-Modified revalidation: the browser keeps
    # the bytes and gets a cheap 304 when the file is unchanged.
    return send_file(
        path,
        mimetype="application/octet-stream",
        conditional=True,
    )
