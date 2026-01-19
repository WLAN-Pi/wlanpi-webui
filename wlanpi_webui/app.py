#!/usr/bin/python3

"""
wlanpi_webui.app
~~~~~~~~~~~~~~~~

the main flask app
"""

import logging
from time import time

from flask import Flask, abort, send_from_directory
from flask_minify import Minify
from werkzeug.middleware.proxy_fix import ProxyFix

from wlanpi_webui.config import Config, get_hostname
from wlanpi_webui.utils import get_dpkg_status_mtime, package_installed


def create_app(config_class=Config):
    app = Flask(__name__)

    Minify(app=app, passive=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    app.config.from_object(config_class)
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

    @app.context_processor
    def inject_vars():
        return {
            "title": f"WLAN Pi: {get_hostname()}",
        }

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
