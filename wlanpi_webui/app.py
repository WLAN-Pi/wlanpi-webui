#!/usr/bin/python3

"""
wlanpi_webui.app
~~~~~~~~~~~~~~~~

the main flask app
"""

import hashlib
import json
import logging
import threading
from datetime import timedelta
from pathlib import Path
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
    active_alerts,
    boot_clock,
    get_dpkg_status_mtime,
    is_beacon_armed,
    is_htmx,
    load_or_create_session_key,
    package_installed,
    read_boot_id,
    system_service_running_state,
)

# Background requests must not refresh the idle timer, or an open tab would
# never time out. htmx polls say so with this header (see app.js); the CLI's
# fetch() polling and automatic shell restarts are listed by endpoint.
POLL_HEADER = "X-Wlanpi-Poll"
BACKGROUND_ENDPOINTS = {
    "cli.output",
    "cli.resize",
    "cli.start",
}

STATIC_ENDPOINTS = ("static", "img")

# Scripts load only from this origin: no inline <script>, no on* handler
# attributes, no eval. WebAssembly (the beacon engine) still compiles.
CONTENT_SECURITY_POLICY = (
    "script-src 'self' 'wasm-unsafe-eval'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'self'"
)


def create_app(config_class=Config):
    app = Flask(__name__)

    # nginx sets X-Forwarded-For and -Proto; it passes Host through and never
    # sets X-Forwarded-Host/-Prefix, so trusting those would let a client
    # rewrite generated URLs.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

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
    # HTTPS only (nginx redirects port 80, but a browser would still send the
    # cookie there in cleartext), and not on cross-site subrequests.
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    app.logger.debug("registering auth blueprint")
    from wlanpi_webui.auth import bp as auth_bp
    from wlanpi_webui.auth.auth import end_session, init_auth, session_is_valid

    init_auth(app)
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

    app.logger.debug("registering cli blueprint")
    from wlanpi_webui.cli import bp as cli_bp

    app.register_blueprint(cli_bp)
    app.logger.debug("cli blueprint registered")

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

    app.logger.debug("registering system blueprint")
    from wlanpi_webui.system import bp as system_bp

    app.register_blueprint(system_bp)
    app.logger.debug("system blueprint registered")

    app.logger.debug("registering dashboard blueprint")
    from wlanpi_webui.dashboard import bp as dashboard_bp

    app.register_blueprint(dashboard_bp)
    app.logger.debug("dashboard blueprint registered")

    app.logger.debug("registering apps blueprint")
    from wlanpi_webui.apps import bp as apps_bp

    app.register_blueprint(apps_bp)
    app.logger.debug("apps blueprint registered")

    app.logger.debug("registering settings blueprint")
    from wlanpi_webui.settings import bp as settings_bp

    app.register_blueprint(settings_bp)
    app.logger.debug("settings blueprint registered")

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

    @app.context_processor
    def inject_beacon():
        # Deliberately uncached (unlike utility_processor): the flag is read at
        # request time so deleting the file disarms the dashboard immediately.
        return {"beacon_armed": is_beacon_armed()}

    @app.before_request
    def enforce_session_freshness():
        # Static files are public and must not touch the session: reading it
        # adds Vary: Cookie and refreshing it sets a new cookie, and together
        # those make browsers refetch every asset on every page.
        if request.endpoint in STATIC_ENDPOINTS:
            return None
        if not session.get("user"):
            return None
        now = boot_clock()
        boot_id = read_boot_id()
        if boot_id and session.get("boot_id") != boot_id:
            end_session()  # the device rebooted
            return None
        if not session_is_valid():
            end_session()  # logged out, revoked, or past MAX_SESSION_AGE
            return None
        last_seen = session.get("last_seen")
        if last_seen is not None and now - last_seen > app.config["IDLE_TIMEOUT"]:
            end_session()  # idle for too long
            return None
        if request.endpoint not in BACKGROUND_ENDPOINTS and not request.headers.get(
            POLL_HEADER
        ):
            session["last_seen"] = now
        return None

    @app.after_request
    def set_content_security_policy(response):
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    # Static URLs carry a hash of the file, so a release or a hand-copied file
    # busts browser caches. The table is built once from the files on disk;
    # nothing on the request path reads a file named by the client.
    static_root = Path(app.static_folder or "")
    fingerprints: dict[str, tuple[Path, int, int, str]] = {}
    for path in static_root.rglob("*"):
        if path.is_file():
            stat = path.stat()
            fingerprints[path.relative_to(static_root).as_posix()] = (
                path,
                stat.st_mtime_ns,
                stat.st_size,
                hashlib.sha256(path.read_bytes()).hexdigest()[:12],
            )

    def static_filename(endpoint, values) -> str | None:
        filename = values.get("filename")
        if not filename:
            return None
        return f"img/{filename}" if endpoint == "img" else filename

    def current_fingerprint(filename: str) -> str | None:
        """The file's hash, or None if it changed since startup."""
        known = fingerprints.get(filename)
        if not known:
            return None
        path, mtime_ns, size, fingerprint = known
        try:
            stat = path.stat()  # the startup path, never one built from input
        except OSError:
            return None
        if (stat.st_mtime_ns, stat.st_size) != (mtime_ns, size):
            return None  # replaced without a restart: stop promising immutable
        return fingerprint

    @app.url_defaults
    def fingerprint_static_urls(endpoint, values):
        if endpoint in STATIC_ENDPOINTS:
            filename = static_filename(endpoint, values)
            fingerprint = current_fingerprint(filename) if filename else None
            if fingerprint:
                values.setdefault("v", fingerprint)

    # A fingerprinted URL never changes, so the browser keeps it without
    # revalidating (one round trip per asset per page adds up over Bluetooth
    # PAN). Other static URLs keep the default revalidation.
    @app.after_request
    def cache_fingerprinted_static(response):
        if (
            request.endpoint in STATIC_ENDPOINTS
            and request.method in ("GET", "HEAD")
            and response.status_code in (200, 304)
        ):
            filename = static_filename(request.endpoint, request.view_args or {})
            known = fingerprints.get(filename) if filename else None
            version = request.args.get("v")
            if known and version == known[3] and current_fingerprint(filename):
                response.headers["Cache-Control"] = (
                    "public, max-age=31536000, immutable"
                )
        return response

    @app.after_request
    def emit_queued_toast(response):
        if request.endpoint in STATIC_ENDPOINTS:
            return response
        # The navbar bell reads the alert keys from every response.
        core_running = _context_cache.get("core_running", True)
        response.headers["X-Wlanpi-Alerts"] = ",".join(
            a["key"] for a in active_alerts(core_running)
        )
        # A queued toast survives redirects and non-HTML responses (e.g. the
        # speedtest report POST), so it rides the next page the user loads.
        if 300 <= response.status_code < 400 or response.mimetype != "text/html":
            return response
        toast = session.pop("wlanpi_toast", None)
        if toast:
            response.headers["X-Wlanpi-Toast"] = json.dumps(toast)
        return response

    @app.before_request
    def require_login():
        if request.endpoint in STATIC_ENDPOINTS:
            return None
        if session.get("user"):
            return None
        if request.endpoint is None:
            return None
        if request.blueprint in ("auth", "errors"):
            return None
        if is_htmx(request) or request.headers.get("X-Requested-With"):
            return "", 401
        return redirect(url_for("auth.login"))

    _context_cache = {}
    _context_cache_time = 0
    _context_cache_mtime = 0
    CONTEXT_CACHE_TTL = 60
    context_lock = threading.Lock()

    def _with_alerts(context):
        # Computed per render so a core failure surfaces promptly; the
        # expensive service/package checks above stay cached.
        alerts = active_alerts(context["core_running"])
        return {
            **context,
            "alerts": alerts,
            "alert_keys": [a["key"] for a in alerts],
        }

    @app.context_processor
    def utility_processor():
        current_time = time()
        current_mtime = get_dpkg_status_mtime()

        def fresh():
            return (
                _context_cache
                and time() - _context_cache_time < CONTEXT_CACHE_TTL
                and _context_cache_mtime == current_mtime
            )

        if fresh():
            return _with_alerts(_context_cache)
        with context_lock:
            # Another thread may have refreshed while this one waited.
            if fresh():
                return _with_alerts(_context_cache)
            return _with_alerts(refresh_context(current_time, current_mtime))

    def refresh_context(current_time, current_mtime):
        nonlocal _context_cache, _context_cache_time, _context_cache_mtime
        _context_cache = {
            "profiler_installed": package_installed("wlanpi-profiler"),
            "kismet_installed": package_installed("kismet"),
            "cockpit_installed": package_installed("cockpit"),
            "grafana_installed": package_installed("grafana"),
            "core_running": system_service_running_state("wlanpi-core", quiet=True),
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
