#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
wlanpi_webui
~~~~~~~
a custom WebUI made to run locally on the WLAN Pi
"""

import logging
from logging.handlers import RotatingFileHandler
from app import create_app

if __name__ == "__main__":
    app = create_app()
    handler = RotatingFileHandler("app.log", maxBytes=10000, backupCount=1)
    handler.setLevel(logging.DEBUG)
    app.logger.addHandler(handler)
    app.run(host="0.0.0.0", port="5000", debug=True)
