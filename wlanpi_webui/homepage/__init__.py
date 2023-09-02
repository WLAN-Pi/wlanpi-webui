from flask import Blueprint

bp = Blueprint("homepage", __name__)

from wlanpi_webui.homepage import homepage
