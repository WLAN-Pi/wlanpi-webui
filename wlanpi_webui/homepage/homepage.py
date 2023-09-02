from flask import render_template, request

from wlanpi_webui.homepage import bp


@bp.route("/")
def homepage():
    base = request.host.split(":")[0]
    url = f"https://{base}/app/librespeed/librespeed_simple.html"
    iframe = f'<iframe class="uk-cover" style="pointer-events: all;" src="{url}" height="100%" width="100%"></iframe>'
    return render_template(
        "/public/iframe.html",
        iframe=iframe,
    )
