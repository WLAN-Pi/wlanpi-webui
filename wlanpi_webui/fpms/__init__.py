from flask import Blueprint

bp = Blueprint("fpms", __name__)

from wlanpi_webui.fpms import networkinfo 
