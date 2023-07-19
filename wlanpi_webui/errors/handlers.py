from flask import current_app, render_template

from wlanpi_webui.errors import bp


@bp.app_errorhandler(404)
def page_not_found(error):
    return (
        render_template(
            "errors/404.html",
            title="Error 404",
        ),
        404,
    )


@bp.app_errorhandler(405)
def page_not_found(error):
    return (
        render_template(
            "errors/405.html",
            title="Error 405",
        ),
        405,
    )


@bp.app_errorhandler(500)
def page_not_found(error):
    return (
        render_template(
            "errors/500.html",
            title="Error 500",
        ),
        500,
    )
