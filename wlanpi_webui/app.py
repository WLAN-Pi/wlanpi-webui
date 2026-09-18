#!/usr/bin/python3

"""
wlanpi_webui.app
~~~~~~~~~~~~~~~~

the main flask app
"""

import logging
from datetime import timedelta
from time import time

from flask import (
    Flask,
    abort,
    redirect,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix

from wlanpi_webui.config import Config, get_hostname
from wlanpi_webui.utils import (
    get_dpkg_status_mtime,
    is_htmx,
    load_or_create_session_key,
    package_installed,
    read_boot_id,
)

# Endpoints polled in the background (stats bar and open nav dropdowns). These
# must not refresh the idle timer, or an open tab would never time out.
BACKGROUND_ENDPOINTS = {
    "stream.stream_stats",
    "profiler.profiler_main_menu",
    "profiler.profiler_side_menu",
    "kismet.kismet_main_menu",
    "kismet.kismet_side_menu",
    "grafana.grafana_main_menu",
    "grafana.grafana_side_menu",
}


def create_app(config_class=Config):
    app = Flask(__name__)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    app.config.from_object(config_class)
    # Persisted key: sessions survive a service restart. A reboot still signs
    # everyone out via the boot id check in enforce_session_freshness.
    app.secret_key = load_or_create_session_key(app.config["SESSION_KEY_PATH"])
    # Idle timeout: the cookie slides only on user activity (see
    # enforce_session_freshness), not on background polling.
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        seconds=app.config["IDLE_TIMEOUT"]
    )
    app.config["SESSION_REFRESH_EACH_REQUEST"] = False

    app.logger.debug("registering auth blueprint")
    from wlanpi_webui.auth import bp as auth_bp

    app.register_blueprint(auth_bp)
    app.logger.debug("auth blueprint registered")

    app.logger.debug("registering errors blueprint")
    from wlanpi_webui.errors import bp as errors_bp

    app.register_blueprint(errors_bp)
    app.logger.debug("errors blueprint registered")

    app.logger.debug("registering librespeed blueprint")
    from wlanpi_webui.librespeed import bp as librespeed_bp

    app.register_blueprint(librespeed_bp)
    app.logger.debug("librespeed blueprint registered")

    app.logger.debug("registering profiler blueprint")
    from wlanpi_webui.profiler import bp as profiler_bp

    app.register_blueprint(profiler_bp)
    app.logger.debug("profiler blueprint registered")

    app.logger.debug("registering network blueprint")
    from wlanpi_webui.network import bp as network_bp

    app.register_blueprint(network_bp)
    app.logger.debug("network blueprint registered")

    app.logger.debug("registering stream blueprint")
    from wlanpi_webui.stream import bp as stream_bp

    app.register_blueprint(stream_bp)
    app.logger.debug("stream blueprint registered")

    app.logger.debug("registering kismet blueprint")
    from wlanpi_webui.kismet import bp as kismet_bp

    app.register_blueprint(kismet_bp)
    app.logger.debug("kismet blueprint registered")

    app.logger.debug("registering cockpit blueprint")
    from wlanpi_webui.cockpit import bp as cockpit_bp

    app.register_blueprint(cockpit_bp)
    app.logger.debug("cockpit blueprint registered")

    app.logger.debug("registering grafana blueprint")
    from wlanpi_webui.grafana import bp as grafana_bp

    app.register_blueprint(grafana_bp)
    app.logger.debug("grafana blueprint registered")

    app.logger.debug("registering about blueprint")
    from wlanpi_webui.about import bp as about_bp

    app.register_blueprint(about_bp)
    app.logger.debug("about blueprint registered")

    app.logger.debug("registering debug blueprint")
    from wlanpi_webui.debug import bp as debug_bp

    app.register_blueprint(debug_bp)
    app.logger.debug("debug blueprint registered")

    app.logger.debug("registering dashboard blueprint")
    from wlanpi_webui.dashboard import bp as dashboard_bp

    app.register_blueprint(dashboard_bp)
    app.logger.debug("dashboard blueprint registered")

    @app.context_processor
    def inject_vars():
        return {
            "title": f"WLAN Pi: {get_hostname()}",
        }

    @app.context_processor
    def inject_csrf_token():
        from wlanpi_webui.auth.auth import get_csrf_token

        return {"csrf_token": get_csrf_token()}

    @app.context_processor
    def inject_current_user():
        return {"current_user": session.get("user")}

    @app.context_processor
    def inject_theme():
        # Theme is persisted in a cookie so it can be rendered server-side
        # (no flash) and survives even when localStorage is unavailable.
        theme = request.cookies.get("wlanpi_theme")
        return {"theme": theme if theme in ("dark", "light") else None}

    @app.before_request
    def enforce_session_freshness():
        if not session.get("user"):
            return None
        now = time()
        boot_id = read_boot_id()
        if boot_id and session.get("boot_id") != boot_id:
            session.clear()  # the device rebooted
            return None
        last_seen = session.get("last_seen")
        if last_seen is not None and now - last_seen > app.config["IDLE_TIMEOUT"]:
            session.clear()  # idle for too long
            return None
        if request.endpoint not in BACKGROUND_ENDPOINTS:
            session["last_seen"] = now
        return None

    @app.before_request
    def require_login():
        if session.get("user"):
            return None
        if request.path.startswith("/static"):
            return None
        if request.endpoint is None:
            return None
        if request.blueprint in ("auth", "errors") or request.endpoint in (
            "static",
            "img",
        ):
            return None
        if is_htmx(request) or request.headers.get("X-Requested-With"):
            return "", 401
        return redirect(url_for("auth.login"))

    _context_cache = {}
    _context_cache_time = 0
    _context_cache_mtime = 0
    CONTEXT_CACHE_TTL = 60

    @app.context_processor
    def utility_processor():
        nonlocal _context_cache, _context_cache_time, _context_cache_mtime

        current_time = time()
        current_mtime = get_dpkg_status_mtime()
        cache_age = current_time - _context_cache_time

        if (
            _context_cache
            and cache_age < CONTEXT_CACHE_TTL
            and _context_cache_mtime == current_mtime
        ):
            return _context_cache

        _context_cache = {
            "profiler_installed": package_installed("wlanpi-profiler"),
            "kismet_installed": package_installed("kismet"),
            "cockpit_installed": package_installed("cockpit"),
            "grafana_installed": package_installed("grafana"),
        }
        _context_cache_time = current_time
        _context_cache_mtime = current_mtime

        return _context_cache

    @app.route("/static/img/<path:filename>")
    def img(filename):
        try:
            return send_from_directory(f"{app.root_path}/static/img/", filename)
        except FileNotFoundError:
            abort(404)

    if not app.debug and not app.testing:
        if app.config["LOG_TO_STDOUT"]:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info("wlanpi_webui startup")

    return app
