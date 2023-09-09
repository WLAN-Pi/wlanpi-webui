from flask import render_template, request

from wlanpi_webui.librespeed import bp
from wlanpi_webui.utils import is_htmx


@bp.route("/")
@bp.route("/speedtest/librespeed")
def librespeed():
    base = request.host.split(":")[0]
    resp_data = {"iframe_url": f"https://{base}/app/librespeed/librespeed_simple.html"}
    if is_htmx(request):
        return render_template("/partials/iframe.html", **resp_data)
    else:
        return render_template("/extends/iframe.html", **resp_data)


@bp.route("/speedtest/librespeed/details")
def librespeed_detailed():
    base = request.host.split(":")[0]
    resp_data = {
        "iframe_url": f"https://{base}/app/librespeed/librespeed_detailed.html"
    }
    if is_htmx(request):
        return render_template("/partials/iframe.html", **resp_data)
    else:
        return render_template("/extends/iframe.html", **resp_data)
