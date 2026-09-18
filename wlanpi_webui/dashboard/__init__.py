from flask import Blueprint

bp = Blueprint("dashboard", __name__)

from wlanpi_webui.dashboard import dashboard
