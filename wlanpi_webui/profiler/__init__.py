from flask import Blueprint

bp = Blueprint("profiler", __name__)

from . import profiler
