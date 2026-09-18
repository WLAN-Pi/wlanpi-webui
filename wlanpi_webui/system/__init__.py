from flask import Blueprint

bp = Blueprint("system", __name__)

from wlanpi_webui.system import system
