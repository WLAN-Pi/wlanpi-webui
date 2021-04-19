from flask import Blueprint

bp = Blueprint("network", __name__)

from . import network
