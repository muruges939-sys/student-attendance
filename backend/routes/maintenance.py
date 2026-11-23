from datetime import datetime

from flask import Blueprint, current_app, request

from auth_utils import auth_required
from db import get_db
from errors import APIError
from holiday_utils import off_day_reason
from responses import success_response

maintenance_bp = Blueprint("maintenance", __name__)


@maintenance_bp.post("/mark-absent")
@auth_required("ADMIN")
def mark_absent():
    """Body (optional): {"date": "YYYY-MM-DD"}. Default: today.
    Today can only be closed after ATTENDANCE_CLOSING_TIME."""
    data = request.get_json(silent=True) or {}
    now = datetime.now()

    if data.get("date"):
        try:
            day = datetime.strptime(data["date"], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            raise APIError("Use date format YYYY-MM-DD.", 400)
    else:
        day = now.date()

    if day > now.date():
        raise APIError("Cannot close a future date.", 400)

    reason = off_day_reason(day)
    if reason:
        raise APIError(f"{day} is a holiday ({reason}). Nothing to mark.", 409)

    if day == now.date():
        try:
            closing = datetime.strptime(current_app.config["ATTENDANCE_CLOSING_TIME"], "%H:%M").time()
        except ValueError:
            raise APIError("ATTENDANCE_CLOSING_TIME in .env must look like 17:00.", 500)
        if now.time() < closing:
            raise APIError(f"Attendance is still open until {closing.strftime('%H:%M')}.", 409)

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO attendance (student_id, attendance_date, status, marked_by) "
            "SELECT s.student_id, %s, 'ABSENT', %s FROM students s "
            "WHERE NOT EXISTS (SELECT 1 FROM attendance a "
            "                  WHERE a.student_id = s.student_id AND a.attendance_date = %s) "
            "AND NOT EXISTS (SELECT 1 FROM leave_requests l "
            "                WHERE l.student_id = s.student_id AND l.status = 'APPROVED' "
            "                AND %s BETWEEN l.start_date AND l.end_date)",
            (day, "SYSTEM", day, day),
        )
        marked = cursor.rowcount
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()

    return success_response(
        f"Marked {marked} student(s) as ABSENT.", {"date": str(day), "marked_absent": marked}
    )