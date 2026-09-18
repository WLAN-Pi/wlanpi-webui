from flask import Blueprint

bp = Blueprint("librespeed", __name__)

from wlanpi_webui.librespeed import librespeed
