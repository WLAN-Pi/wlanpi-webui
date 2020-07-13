from flask import render_template, current_app
from wlanpi_webui.errors import bp

@bp.app_errorhandler(404)
def page_not_found(error):
    return (
        render_template(
            "errors/404.html",
            title="error",
            wlanpi_version=current_app.config['WLANPI_VERSION'],
            webui_version=current_app.config['WEBUI_VERSION'],
        ),
        404,
    )

@bp.app_errorhandler(500)
@bp.app_errorhandler(505)
def page_not_found(error):
    return (
        render_template(
            "errors/500.html",
            title="error",
            wlanpi_version=current_app.config['WLANPI_VERSION'],
            webui_version=current_app.config['WEBUI_VERSION'],
        ),
        404,
    )
