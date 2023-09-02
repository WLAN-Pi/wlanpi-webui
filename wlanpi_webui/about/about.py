from flask import render_template

from wlanpi_webui.about import bp


@bp.route("/about")
def about():
    return render_template(
        "public/about.html",
    )
