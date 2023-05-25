from flask import current_app, render_template, request

from wlanpi_webui.cockpit import bp

@bp.route("/cockpit")
def cockpit():
    COCKPIT_PORT = "9090"
    base = request.host.split(":")[0]
    #return redirect(f"http://{base}:{KISMET_PORT}")
    return render_template('/public/kismet.html', iframe=f"http://{base}:{COCKPIT_PORT}")
