from flask import Blueprint

bp = Blueprint("network", __name__)

from wlanpi_webui.network import network 
