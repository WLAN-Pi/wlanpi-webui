#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
wlanpi_webui.app
~~~~~~~~~~~~~~~~

the main flask app
"""

import logging
import subprocess

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

    def kismet_status():
        """
        Checks the status of the Kismet service.
        Returns true if Kismet is running, false otherwise.
        """
        try:
            # this cmd fails if service not installed
            cmd = "/bin/systemctl is-active --quiet kismet"
            subprocess.run(cmd, shell=True).check_returncode()
        except:
            # cmd failed, so profiler service not installed
            return False

        return True

    def kismet_message():
        """
        Checks if Kismet is running.
        Returns 'Kismet is running' if it is, and 'Kismet is not running' if not.
        """
        status = kismet_status()
        if status:
            return "Kismet is running"
        else:
            return "Kismet is not running"

    @app.route("/service-unavailable")
    def service_down():
        return "<html><p>Service unavailable. Please start it on the device.</p></html>"

    @app.context_processor
    def inject_vars():
        base = request.host.split(":")[0]
        return {
            "hostname": Config.HOSTNAME,
            "wlanpi_version": Config.WLANPI_VERSION,
            "webui_version": Config.WEBUI_VERSION,
            "title": Config.TITLE,
            "cockpit_iframe": f"https://{base}:9090",
            "kismet_iframe": (
                f"http://{base}:2501"
                if kismet_status()
                else f"http://{base}/service-unavailable"
            ),
            "grafana_iframe": f"http://{base}:3000",
            "kismet_message": f"{kismet_message()}",
            "kismet_status": kismet_status(),
        }

    @app.route("/<task>kismet")
    def start_stop_kismet(task):
        if task == "start":
            try:
                cmd = "/bin/systemctl start kismet"
                subprocess.run(cmd, shell=True, timeout=10)
                base = request.host.split(":")[0]
                return redirect(f"http://{base}")
            except:
                return redirect(f"http://{base}")
        elif task == "stop":
            try:
                cmd = "/bin/systemctl stop kismet"
                subprocess.run(cmd, shell=True, timeout=10)
                base = request.host.split(":")[0]
                return redirect(f"http://{base}")
            except:
                return redirect(f"http://{base}")

    @app.route("/terminal")
    def terminal():
        COCKPIT_PORT = "9090"
        base = request.host.split(":")[0]
        return redirect(f"http://{base}:{COCKPIT_PORT}/system/terminal")

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
