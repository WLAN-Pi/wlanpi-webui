from flask import Blueprint

bp = Blueprint("apps", __name__)

from wlanpi_webui.apps import apps
