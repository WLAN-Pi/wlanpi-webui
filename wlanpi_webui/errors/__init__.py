from flask import Blueprint

bp = Blueprint("errors", __name__)

from wlanpi_webui.errors import handlers  # noqa: F401
