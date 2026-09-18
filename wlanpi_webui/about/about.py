from flask import render_template, request

from wlanpi_webui.about import bp
from wlanpi_webui.utils import is_htmx


@bp.route("/about")
def about():
    if is_htmx(request):
        return render_template("/partials/about.html")
    else:
        return render_template("/extends/about.html")
