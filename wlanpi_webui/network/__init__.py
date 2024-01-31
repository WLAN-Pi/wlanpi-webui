from flask import Blueprint

bp = Blueprint("network", __name__)

from wlanpi_webui.network import network_info  # noqa: F401
from wlanpi_webui.network import network_setup  # noqa: F401
