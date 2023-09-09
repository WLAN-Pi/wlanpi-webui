from flask import render_template

from wlanpi_webui.errors import bp


@bp.app_errorhandler(404)
@bp.route("/404")
def page_not_found_404(error=None):
    return (
        render_template(
            "errors/404.html",
            title="Error 404",
        ),
        404,
    )


@bp.app_errorhandler(405)
@bp.route("/405")
def page_not_found_405(error=None):
    return (
        render_template(
            "errors/405.html",
            title="Error 405",
        ),
        405,
    )


@bp.app_errorhandler(418)
@bp.route("/418")
def page_not_found_418(error=None):
    return (
        render_template(
            "errors/418.html",
            title="Error 418",
        ),
        404,
    )


@bp.app_errorhandler(500)
@bp.route("/500")
def page_not_found_500(error=None):
    return (
        render_template(
            "errors/500.html",
            title="Error 500",
        ),
        500,
    )
