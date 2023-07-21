from flask import render_template, request

from wlanpi_webui.librespeed import bp


@bp.route("/librespeed")
def librespeed():
    base = request.host.split(":")[0]
    iframe = f"https://{base}/app/librespeed/librespeed_simple.html"
    return render_template(
        "/public/iframe.html",
        iframe=iframe,
    )


@bp.route("/librespeed2")
def librespeed2():
    base = request.host.split(":")[0]
    iframe = f"https://{base}/app/librespeed/librespeed_detailed.html"
    return render_template(
        "/public/iframe.html",
        iframe=iframe,
    )
