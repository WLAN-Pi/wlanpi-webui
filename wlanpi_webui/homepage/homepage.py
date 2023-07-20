from flask import render_template, request

from wlanpi_webui.homepage import bp


@bp.route("/")
def homepage():
    base = request.host.split(":")[0]
    speedtest = f"http://{base}/app/librespeed/librespeed_detailed.html"
    return render_template("/public/home.html", speedtest=speedtest)
