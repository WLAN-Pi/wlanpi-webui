#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
wlanpi_webui
~~~~~~~~~~~~

a custom WebUI made to run locally on the WLAN Pi
"""

import logging
from logging.handlers import RotatingFileHandler

from wlanpi_webui.app import create_app

if __name__ == "__main__":
    app = create_app()
    log_filename = "app.log"
    logging.basicConfig(
        filename=log_filename,
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s",
    )
    handler = RotatingFileHandler(log_filename, maxBytes=10000, backupCount=2)
    handler.setLevel(logging.DEBUG)
    app.logger.addHandler(handler)
    app.run(
        host="0.0.0.0",
        port="5000",
        debug=True,
        # ssl_context=(
        #     "/etc/nginx/ssl/self-signed-wlanpi.cert",
        #     "/etc/nginx/ssl/self-signed-wlanpi.key",
        # ),
    )
