# -*- coding: utf-8 -*-

# activate venv, make sure flask app is installed in venv
activate_this = "/opt/wlanpi/wlanpi-webui/venv/bin/activate_this.py"
with open(activate_this) as _file:
    exec(_file.read(), dict(__file__=activate_this))

from wlanpi_webui import create_app

application = create_app()
