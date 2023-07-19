from flask import Blueprint

bp = Blueprint("cockpit", __name__)

from wlanpi_webui.cockpit import cockpit
