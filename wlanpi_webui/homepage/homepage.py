from flask import render_template, request

from wlanpi_webui.homepage import bp


@bp.route("/")
def homepage():
    base = request.host.split(":")[0]
    iframe = f"https://{base}/app/librespeed/librespeed_simple.html"
    return render_template("/public/iframe.html", iframe=iframe)
