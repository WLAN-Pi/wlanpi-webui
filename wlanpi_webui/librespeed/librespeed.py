from flask import redirect

from wlanpi_webui.librespeed import bp


@bp.route("/speedtest/librespeed")
def librespeed():
    return redirect("/app/librespeed/librespeed_simple.html")


@bp.route("/speedtest/librespeed/details")
def librespeed_detailed():
    return redirect("/app/librespeed/librespeed_detailed.html")
