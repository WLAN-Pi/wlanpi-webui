from flask import Blueprint

bp = Blueprint("kismet", __name__)

from wlanpi_webui.kismet import kismet
