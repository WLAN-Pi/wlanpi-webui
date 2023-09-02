from flask import render_template, request

from wlanpi_webui.librespeed import bp


@bp.route("/librespeed")
def librespeed():
    base = request.host.split(":")[0]
    url = f"https://{base}/app/librespeed/librespeed_simple.html"
    iframe = f'<iframe class="uk-cover" style="pointer-events: all;" src="{url}" height="100%" width="100%"></iframe>'
    return render_template(
        "/public/iframe.html",
        iframe=iframe,
    )


@bp.route("/librespeed2")
def librespeed2():
    base = request.host.split(":")[0]
    url = f"https://{base}/app/librespeed/librespeed_detailed.html"
    iframe = f'<iframe class="uk-cover" style="pointer-events: all;" src="{url}" height="100%" width="100%"></iframe>'
    return render_template(
        "/public/iframe.html",
        iframe=iframe,
    )
