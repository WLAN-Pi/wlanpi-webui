from flask import Blueprint

bp = Blueprint("settings", __name__)

from wlanpi_webui.settings import settings
