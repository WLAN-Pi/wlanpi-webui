from flask import Blueprint

bp = Blueprint("profiler", __name__)

from wlanpi_webui.profiler import profiler
