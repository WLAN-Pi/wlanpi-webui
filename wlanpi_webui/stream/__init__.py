from flask import Blueprint

bp = Blueprint("stream", __name__)

from wlanpi_webui.stream import stream
