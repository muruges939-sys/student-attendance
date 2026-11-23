from flask import Blueprint, current_app
from mysql.connector import Error as MySQLError

from db import query_one
from responses import error_response, success_response

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    try:
        row = query_one("SELECT DATABASE() AS database_name")
    except MySQLError:
        current_app.logger.exception("Health check: database connection failed")
        return error_response(
            "Backend is running, but the database connection failed. "
            "Check the DB_ settings in your .env file.",
            503,
        )

    return success_response(
        "Backend is running and the database is connected.",
        {"database": row["database_name"]},
    )