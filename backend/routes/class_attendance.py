from datetime import datetime

from flask import Blueprint, g, request

from auth_utils import auth_required
from db import execute, query_all, query_one
from errors import APIError
from responses import success_response

class_attendance_bp = Blueprint("class_attendance", __name__)

STATUSES = ("PRESENT", "HALF_DAY", "ABSENT", "INCOMPLETE", "SL", "CL")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _clean(row):
    for key in ("attendance_date", "check_in", "check_out", "created_at", "updated_at"):
        if row.get(key) is not None:
            row[key] = str(row[key])
    return row


def _get_student_or_404(student_id):
    student = query_one(
        "SELECT student_id, name, department, year, section FROM students WHERE student_id = %s",
        (student_id,),
    )
    user = g.current_user
    if not student:
        raise APIError("Student not found.", 404)
    if user["role"] == "FACULTY" and not (
        student["department"] == user["department"]
        and student["year"] == user["year"]
        and student["section"] == user["section"]
    ):
        raise APIError("Student not found.", 404)
    return student


@class_attendance_bp.get("")
@auth_required("ADMIN", "FACULTY")
def class_attendance():
    """GET /api/class-attendance?date=YYYY-MM-DD  (default: today)"""
    date_text = request.args.get("date")
    day = _parse_date(date_text) if date_text else datetime.now().date()
    if day is None:
        raise APIError("Use date format YYYY-MM-DD.", 400)

    user = g.current_user
    sql = (
        "SELECT s.student_id, s.name, s.department, s.year, s.section, "
        "a.id AS attendance_id, a.check_in, a.check_out, a.status, a.marked_by "
        "FROM students s LEFT JOIN attendance a "
        "ON a.student_id = s.student_id AND a.attendance_date = %s "
    )
    params = [day]
    if user["role"] == "FACULTY":
        sql += "WHERE s.department = %s AND s.year = %s AND s.section = %s "
        params += [user["department"], user["year"], user["section"]]
    sql += "ORDER BY s.student_id"

    rows = query_all(sql, tuple(params))
    for r in rows:
        r["status"] = r["status"] or "NOT_MARKED"
        for key in ("check_in", "check_out"):
            if r[key] is not None:
                r[key] = str(r[key])
    return success_response(
        "Class attendance.", {"date": str(day), "students": rows, "count": len(rows)}
    )


@class_attendance_bp.get("/student/<student_id>")
@auth_required("ADMIN", "FACULTY")
def student_history(student_id):
    _get_student_or_404(student_id)
    rows = query_all(
        "SELECT * FROM attendance WHERE student_id = %s ORDER BY attendance_date DESC",
        (student_id,),
    )
    return success_response(
        "Attendance history.", {"records": [_clean(r) for r in rows], "count": len(rows)}
    )


@class_attendance_bp.put("/student/<student_id>")
@auth_required("ADMIN", "FACULTY")
def edit_attendance(student_id):
    """Body: {"date": "YYYY-MM-DD", "status": "PRESENT", "check_in": "09:00", "check_out": "16:00"}
    check_in / check_out are optional."""
    student = _get_student_or_404(student_id)
    data = request.get_json(silent=True) or {}
    errors = {}

    day = _parse_date(data.get("date"))
    if day is None:
        errors["date"] = "Use format YYYY-MM-DD."
    elif day > datetime.now().date():
        errors["date"] = "Cannot mark attendance for a future date."

    status = data.get("status")
    if status not in STATUSES:
        errors["status"] = "status must be one of: " + ", ".join(STATUSES)

    times = {}
    for field in ("check_in", "check_out"):
        value = data.get(field)
        if value is None:
            continue
        try:
            times[field] = datetime.strptime(value, "%H:%M").time()
        except (TypeError, ValueError):
            errors[field] = "Use format HH:MM (24 hour)."
    if errors:
        raise APIError("Validation failed.", 400, errors)

    if status in ("SL", "CL"):
        leave = query_one(
            "SELECT id FROM leave_requests WHERE student_id = %s AND status = 'APPROVED' "
            "AND %s BETWEEN start_date AND end_date",
            (student_id, day),
        )
        if not leave:
            raise APIError("SL/CL can only be set through an approved leave request.", 409)
    else:
        leave = query_one(
            "SELECT id FROM leave_requests WHERE student_id = %s AND status = 'APPROVED' "
            "AND %s BETWEEN start_date AND end_date",
            (student_id, day),
        )
        if leave:
            raise APIError("Student has approved leave on this date.", 409)

    editor = g.current_user["name"]
    execute(
        "INSERT INTO attendance (student_id, attendance_date, check_in, check_out, status, marked_by) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE status = VALUES(status), marked_by = VALUES(marked_by), "
        "check_in = COALESCE(VALUES(check_in), check_in), "
        "check_out = COALESCE(VALUES(check_out), check_out)",
        (student_id, day, times.get("check_in"), times.get("check_out"), status, editor),
    )
    execute(
        "INSERT INTO notifications (student_id, title, message, type) VALUES (%s, %s, %s, %s)",
        (
            student_id,
            "Attendance updated",
            f"Your attendance for {day} was marked as {status} by {editor}.",
            "ATTENDANCE_UPDATE",
        ),
    )
    record = query_one(
        "SELECT * FROM attendance WHERE student_id = %s AND attendance_date = %s", (student_id, day)
    )
    return success_response("Attendance updated.", {"attendance": _clean(record)})