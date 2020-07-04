from flask import Blueprint

bp = Blueprint("speedtest", __name__)

from wlanpi_webui.speedtest import speedtest
