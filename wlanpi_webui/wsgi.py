#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
wlanpi_webui.wsgi
~~~~~~~~~~~~~~~~~
a custom local WebUI made for the WLAN Pi

run this from gunicorn
"""

from wlanpi_webui.app import create_app

app = create_app()
