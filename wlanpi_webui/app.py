#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
wlanpi_webui.app
~~~~~~~~~~~~~~~~

the main flask app
"""

import logging

from flask import Flask, abort, request, send_from_directory

from wlanpi_webui.config import Config
from wlanpi_webui.utils import systemd_service_message, systemd_service_status


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.logger.debug("app.py create_app reached")

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

    app.logger.debug("registering homepage blueprint")
    from wlanpi_webui.homepage import bp as homepage_bp

    app.register_blueprint(homepage_bp)
    app.logger.debug("homepage blueprint registered")

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
        base = request.host.split(":")[0]
        return {
            "hostname": Config.HOSTNAME,
            "wlanpi_version": Config.WLANPI_VERSION,
            "webui_version": Config.WEBUI_VERSION,
            "title": Config.TITLE,
            "profiler_message": systemd_service_message("wlanpi-profiler"),
            "profiler_status": systemd_service_status("wlanpi-profiler"),
            "kismet_message": systemd_service_message("kismet"),
            "kismet_status": systemd_service_status("kismet"),
            "grafana_message": systemd_service_message("grafana-server"),
            "grafana_status": systemd_service_status("grafana-server"),
        }

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
