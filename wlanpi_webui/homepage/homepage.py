from flask import current_app, render_template, request, Response

from wlanpi_webui.homepage import bp



@bp.route("/")
def homepage():
    spt_port = "8080"
    base = request.host.split(":")[0]
    speedtest = f"http://{base}:{spt_port}/librespeed_detailed.html"
    return render_template(
        "/public/home.html",
        speedtest=speedtest)