from datetime import datetime

import mysql.connector
from flask import Blueprint, request

from auth_utils import auth_required
from db import execute, query_all, query_one
from errors import APIError
from responses import success_response

holidays_bp = Blueprint("holidays", __name__)


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _clean(row):
    row["holiday_date"] = str(row["holiday_date"])
    row["created_at"] = str(row["created_at"])
    return row


@holidays_bp.get("")
@auth_required()
def list_holidays():
    rows = query_all("SELECT holiday_date, description, created_at FROM holidays ORDER BY holiday_date")
    return success_response("Holidays fetched.", {"holidays": [_clean(r) for r in rows], "count": len(rows)})


@holidays_bp.post("")
@auth_required("ADMIN")
def add_holiday():
    data = request.get_json(silent=True) or {}
    errors = {}
    day = _parse_date(data.get("date"))
    if day is None:
        errors["date"] = "Use format YYYY-MM-DD."
    desc = data.get("description")
    if not isinstance(desc, str) or not desc.strip() or len(desc.strip()) > 100:
        errors["description"] = "description is required (max 100 characters)."
    if errors:
        raise APIError("Validation failed.", 400, errors)

    try:
        execute("INSERT INTO holidays (holiday_date, description) VALUES (%s, %s)", (day, desc.strip()))
    except mysql.connector.IntegrityError:
        raise APIError("That date is already a holiday.", 409)
    row = query_one("SELECT holiday_date, description, created_at FROM holidays WHERE holiday_date = %s", (day,))
    return success_response("Holiday added.", {"holiday": _clean(row)}, 201)


@holidays_bp.delete("/<date_text>")
@auth_required("ADMIN")
def delete_holiday(date_text):
    day = _parse_date(date_text)
    if day is None:
        raise APIError("Use format YYYY-MM-DD.", 400)
    if not query_one("SELECT holiday_date FROM holidays WHERE holiday_date = %s", (day,)):
        raise APIError("Holiday not found.", 404)
    execute("DELETE FROM holidays WHERE holiday_date = %s", (day,))
    return success_response("Holiday deleted.")