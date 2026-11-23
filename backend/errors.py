from mysql.connector import Error as MySQLError
from werkzeug.exceptions import HTTPException

from responses import error_response


class APIError(Exception):
    """Raise this anywhere to return a clean JSON error to the client."""

    def __init__(self, message, status_code=400, errors=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(e):
        return error_response(e.message, e.status_code, e.errors)

    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        # Covers 400, 401, 403, 404, 405, etc.
        return error_response(e.description, e.code)

    @app.errorhandler(MySQLError)
    def handle_database_error(e):
        app.logger.exception("Database error")
        return error_response("A database error occurred.", 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        app.logger.exception("Unexpected error")
        return error_response("Internal server error.", 500)