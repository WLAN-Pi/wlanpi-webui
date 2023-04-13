from flask import current_app, render_template, request

from wlanpi_webui.kismet import bp

@bp.route("/kismet")
def kismet():
    KISMET_PORT = "2501"
    base = request.host.split(":")[0]
    #return redirect(f"http://{base}:{KISMET_PORT}")
    return render_template('/public/kismet.html', iframe=f"http://{base}:{KISMET_PORT}")
