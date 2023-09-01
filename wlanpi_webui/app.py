#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
wlanpi_webui.app
~~~~~~~~~~~~~~~~

the main flask app
"""

import logging
import subprocess

import requests
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

    app.logger.debug("registering about blueprint")
    from wlanpi_webui.about import bp as about_bp

    app.register_blueprint(about_bp)
    app.logger.debug("about blueprint registered")

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
            # cmd failed, so kismit service not installed
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
            "cockpit_iframe": f"https://{base}/app/cockpit",
            "kismet_iframe": (
                f"https://{base}/app/kismet"
                if kismet_status()
                else f"https://{base}/service-unavailable"
            ),
            "grafana_iframe": f"https://{base}:3000/app/grafana",
            "kismet_message": f"{kismet_message()}",
            "kismet_status": kismet_status(),
        }

    @app.route("/<task>kismet")
    def start_stop_kismet(task):
        proto = request.host_url.split(":")[0]
        base = request.host.split(":")[0]
        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
        }
        params = {
            "name": "kismet",
        }
        if task == "start":
            try:
                requests.post(
                    "http://127.0.0.1:31415/api/v1/system/service/start",
                    params=params,
                    headers=headers,
                )
                return redirect(request.referrer)
            except:
                return redirect(request.referrer)
        elif task == "stop":
            try:
                requests.post(
                    "http://127.0.0.1:31415/api/v1/system/service/stop",
                    params=params,
                    headers=headers,
                )
                return redirect(request.referrer)
            except:
                return redirect(request.referrer)

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
