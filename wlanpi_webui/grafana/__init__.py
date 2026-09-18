from flask import Blueprint

bp = Blueprint("grafana", __name__)

from wlanpi_webui.grafana import grafana
