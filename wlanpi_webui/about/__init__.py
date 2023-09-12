from flask import Blueprint

bp = Blueprint("about", __name__)

from wlanpi_webui.about import about  # noqa: F401
