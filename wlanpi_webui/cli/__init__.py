from flask import Blueprint

bp = Blueprint("cli", __name__)

from wlanpi_webui.cli import cli
