from flask import render_template, request

from wlanpi_webui.librespeed import bp


@bp.route("/")
@bp.route("/librespeed")
def librespeed():
    base = request.host.split(":")[0]

    resp_data = {"iframe_url": f"https://{base}/app/librespeed/librespeed_simple.html"}
    htmx_request = request.headers.get("HX-Request") is not None
    if htmx_request:
        return render_template("/public/partial_iframe.html", **resp_data)
    else:
        return render_template("/public/iframe.html", **resp_data)


@bp.route("/librespeed2")
def librespeed2():
    base = request.host.split(":")[0]

    resp_data = {
        "iframe_url": f"https://{base}/app/librespeed/librespeed_detailed.html"
    }

    htmx_request = request.headers.get("HX-Request") is not None
    if htmx_request:
        return render_template("/public/partial_iframe.html", **resp_data)
    else:
        return render_template("/public/iframe.html", **resp_data)
