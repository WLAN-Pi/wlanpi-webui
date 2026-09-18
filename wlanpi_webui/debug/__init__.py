from flask import Blueprint

bp = Blueprint("debug", __name__)

from wlanpi_webui.debug import debug
