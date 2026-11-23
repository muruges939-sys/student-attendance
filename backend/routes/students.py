import re

import mysql.connector
from flask import Blueprint, g, request

from auth_utils import auth_required
from db import execute, query_all, query_one
from errors import APIError
from responses import success_response

students_bp = Blueprint("students", __name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
COLUMNS = "id, student_id, name, email, department, year, section, created_at"


def _validate_student(data, partial=False):
    """Returns cleaned dict. Raises APIError if invalid."""
    errors = {}
    clean = {}

    for field in ("student_id", "name", "email", "department", "section"):
        if field not in data:
            if not partial and field in ("student_id", "name", "email"):
                errors[field] = f"{field} is required."
            continue
        value = data[field]
        if not isinstance(value, str) or not value.strip():
            errors[field] = f"{field} must be a non-empty text."
            continue
        clean[field] = value.strip()

    if "email" in clean:
        clean["email"] = clean["email"].lower()
        if not EMAIL_PATTERN.match(clean["email"]):
            errors["email"] = "Invalid email format."
    if "student_id" in clean and len(clean["student_id"]) > 20:
        errors["student_id"] = "student_id must be 20 characters or less."

    if "year" in data:
        if isinstance(data["year"], int) and not isinstance(data["year"], bool) and 1 <= data["year"] <= 6:
            clean["year"] = data["year"]
        else:
            errors["year"] = "year must be a number between 1 and 6."

    if errors:
        raise APIError("Validation failed.", 400, errors)
    return clean


def _can_access(student):
    """Admin: any student. Faculty: only own class."""
    user = g.current_user
    if user["role"] == "ADMIN":
        return True
    return (
        student["department"] == user["department"]
        and student["year"] == user["year"]
        and student["section"] == user["section"]
    )


def _get_student_or_404(student_id):
    student = query_one(f"SELECT {COLUMNS} FROM students WHERE student_id = %s", (student_id,))
    if not student or not _can_access(student):
        raise APIError("Student not found.", 404)
    return student


@students_bp.get("")
@auth_required("ADMIN", "FACULTY")
def list_students():
    user = g.current_user
    if user["role"] == "FACULTY":
        rows = query_all(
            f"SELECT {COLUMNS} FROM students "
            "WHERE department = %s AND year = %s AND section = %s ORDER BY student_id",
            (user["department"], user["year"], user["section"]),
        )
    else:
        rows = query_all(f"SELECT {COLUMNS} FROM students ORDER BY student_id")
    return success_response("Students fetched.", {"students": rows, "count": len(rows)})


@students_bp.get("/<student_id>")
@auth_required("ADMIN", "FACULTY")
def get_student(student_id):
    return success_response("Student fetched.", {"student": _get_student_or_404(student_id)})


@students_bp.post("")
@auth_required("ADMIN")
def add_student():
    clean = _validate_student(request.get_json(silent=True) or {})
    try:
        execute(
            "INSERT INTO students (student_id, name, email, department, year, section) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                clean["student_id"], clean["name"], clean["email"],
                clean.get("department"), clean.get("year"), clean.get("section"),
            ),
        )
    except mysql.connector.IntegrityError:
        raise APIError("student_id or email already exists.", 409)
    student = query_one(f"SELECT {COLUMNS} FROM students WHERE student_id = %s", (clean["student_id"],))
    return success_response("Student added.", {"student": student}, 201)


@students_bp.put("/<student_id>")
@auth_required("ADMIN")
def update_student(student_id):
    _get_student_or_404(student_id)
    clean = _validate_student(request.get_json(silent=True) or {}, partial=True)
    clean.pop("student_id", None)  # student_id cannot be changed
    if not clean:
        raise APIError("No valid fields to update.", 400)

    assignments = ", ".join(f"{col} = %s" for col in clean)  # column names come from our code, not the client
    try:
        execute(f"UPDATE students SET {assignments} WHERE student_id = %s", (*clean.values(), student_id))
    except mysql.connector.IntegrityError:
        raise APIError("That email already exists.", 409)
    return success_response("Student updated.", {"student": _get_student_or_404(student_id)})


@students_bp.delete("/<student_id>")
@auth_required("ADMIN")
def delete_student(student_id):
    _get_student_or_404(student_id)
    try:
        execute("DELETE FROM students WHERE student_id = %s", (student_id,))
    except mysql.connector.IntegrityError:
        raise APIError(
            "Cannot delete: this student has attendance, leave or notification records.", 409
        )
    return success_response("Student deleted.")