from flask import Blueprint

bp = Blueprint("speedtest", __name__)

from . import speedtest
