from flask import render_template, request

from wlanpi_webui.librespeed import bp


@bp.route("/librespeed")
def librespeed():
    base = request.host.split(":")[0]
    iframe = f"http://{base}/app/librespeed/librespeed_simple.html"
    return render_template(
        "/public/librespeed.html",
        iframe=iframe,
    )


@bp.route("/librespeed2")
def librespeed2():
    base = request.host.split(":")[0]
    iframe = f"http://{base}/app/librespeed/librespeed_detailed.html"
    return render_template(
        "/public/librespeed.html",
        iframe=iframe,
    )
