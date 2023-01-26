#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
wlanpi_webui.app
~~~~~~~~~~~~~~~~

the main flask app
"""

import logging

from flask import Flask, abort, redirect, request, send_from_directory

from wlanpi_webui.config import Config


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

    @app.route("/admin")
    def admin():
        COCKPIT_PORT = "9090"
        base = request.host.split(":")[0]
        return redirect(f"http://{base}:{COCKPIT_PORT}")

    @app.route("/terminal")
    def terminal():
        COCKPIT_PORT = "9090"
        base = request.host.split(":")[0]
        return redirect(f"http://{base}:{COCKPIT_PORT}/system/terminal")

    @app.route("/kismet")
    def kismet():
        KISMET_PORT = "2501"
        base = request.host.split(":")[0]
        return redirect(f"http://{base}:{KISMET_PORT}")

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
