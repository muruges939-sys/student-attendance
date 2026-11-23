import mysql.connector
from flask import Blueprint, g, request
from werkzeug.security import generate_password_hash

from auth_utils import auth_required
from db import execute, query_all, query_one
from errors import APIError
from responses import success_response

faculty_bp = Blueprint("faculty", __name__)

COLUMNS = "id, name, username, role, department, year, section, created_at"


def _clean(row):
    if row.get("created_at") is not None:
        row["created_at"] = str(row["created_at"])
    return row


def _get_faculty_or_404(faculty_id):
    row = query_one(
        f"SELECT {COLUMNS} FROM users WHERE id = %s AND role = 'FACULTY'", (faculty_id,)
    )
    if not row:
        raise APIError("Faculty not found.", 404)
    return row


def _validate(data, partial=False):
    errors, clean = {}, {}

    for field in ("name", "username", "department", "section"):
        required = not partial
        if field not in data:
            if required:
                errors[field] = f"{field} is required."
            continue
        value = data[field]
        if not isinstance(value, str) or not value.strip():
            errors[field] = f"{field} must be a non-empty text."
        else:
            clean[field] = value.strip()

    if "username" in clean and len(clean["username"]) > 50:
        errors["username"] = "username must be 50 characters or less."

    if "year" not in data:
        if not partial:
            errors["year"] = "year is required."
    else:
        y = data["year"]
        if isinstance(y, int) and not isinstance(y, bool) and 1 <= y <= 6:
            clean["year"] = y
        else:
            errors["year"] = "year must be a number between 1 and 6."

    if "password" in data:
        pw = data["password"]
        if not isinstance(pw, str) or len(pw) < 8:
            errors["password"] = "password must be at least 8 characters."
        else:
            clean["password"] = pw
    elif not partial:
        errors["password"] = "password is required."

    if errors:
        raise APIError("Validation failed.", 400, errors)
    return clean


@faculty_bp.get("")
@auth_required("ADMIN")
def list_faculty():
    rows = query_all(f"SELECT {COLUMNS} FROM users WHERE role = 'FACULTY' ORDER BY name")
    return success_response("Faculty fetched.", {"faculty": [_clean(r) for r in rows], "count": len(rows)})


@faculty_bp.get("/<int:faculty_id>")
@auth_required("ADMIN")
def get_faculty(faculty_id):
    return success_response("Faculty fetched.", {"faculty": _clean(_get_faculty_or_404(faculty_id))})


@faculty_bp.post("")
@auth_required("ADMIN")
def add_faculty():
    clean = _validate(request.get_json(silent=True) or {})
    try:
        new_id = execute(
            "INSERT INTO users (name, username, password_hash, role, department, year, section) "
            "VALUES (%s, %s, %s, 'FACULTY', %s, %s, %s)",
            (
                clean["name"], clean["username"], generate_password_hash(clean["password"]),
                clean["department"], clean["year"], clean["section"],
            ),
        )
    except mysql.connector.IntegrityError:
        raise APIError("That username already exists.", 409)
    return success_response("Faculty added.", {"faculty": _clean(_get_faculty_or_404(new_id))}, 201)


@faculty_bp.put("/<int:faculty_id>")
@auth_required("ADMIN")
def update_faculty(faculty_id):
    _get_faculty_or_404(faculty_id)
    clean = _validate(request.get_json(silent=True) or {}, partial=True)
    if "password" in clean:
        clean["password_hash"] = generate_password_hash(clean.pop("password"))
    if not clean:
        raise APIError("No valid fields to update.", 400)

    assignments = ", ".join(f"{col} = %s" for col in clean)  # column names come from our code only
    try:
        execute(f"UPDATE users SET {assignments} WHERE id = %s", (*clean.values(), faculty_id))
    except mysql.connector.IntegrityError:
        raise APIError("That username already exists.", 409)
    return success_response("Faculty updated.", {"faculty": _clean(_get_faculty_or_404(faculty_id))})


@faculty_bp.delete("/<int:faculty_id>")
@auth_required("ADMIN")
def delete_faculty(faculty_id):
    _get_faculty_or_404(faculty_id)
    execute("DELETE FROM users WHERE id = %s", (faculty_id,))
    return success_response("Faculty deleted.")