from datetime import datetime

from flask import Blueprint, current_app, g

from auth_utils import auth_required
from db import execute, query_all, query_one
from errors import APIError
from holiday_utils import off_day_reason
from responses import success_response

attendance_bp = Blueprint("attendance", __name__)


def _cfg_time(name):
    try:
        return datetime.strptime(current_app.config[name], "%H:%M").time()
    except ValueError:
        raise APIError(f"{name} in .env must look like 09:00.", 500)


def _today_row(student_id):
    return query_one(
        "SELECT * FROM attendance WHERE student_id = %s AND attendance_date = CURDATE()",
        (student_id,),
    )


def _clean(row):
    if not row:
        return row
    for key in ("check_in", "check_out", "attendance_date", "created_at", "updated_at"):
        if row.get(key) is not None:
            row[key] = str(row[key])
    return row


def _approved_leave_today(student_id):
    return query_one(
        "SELECT id FROM leave_requests WHERE student_id = %s AND status = 'APPROVED' "
        "AND CURDATE() BETWEEN start_date AND end_date",
        (student_id,),
    )


@attendance_bp.post("/check-in")
@auth_required("STUDENT")
def check_in():
    sid = g.current_user["student_id"]
    now = datetime.now()

    reason = off_day_reason(now.date())
    if reason:
        raise APIError(f"Today is a holiday ({reason}).", 409)
    if _approved_leave_today(sid):
        raise APIError("You are on approved leave today.", 409)
    if _today_row(sid):
        raise APIError("Attendance for today is already recorded.", 409)

    start, closing = _cfg_time("COLLEGE_START_TIME"), _cfg_time("ATTENDANCE_CLOSING_TIME")
    if now.time() < start:
        raise APIError(f"Check-in opens at {start.strftime('%H:%M')}.", 409)
    if now.time() >= closing:
        raise APIError("Attendance is closed for today.", 409)

    execute(
        "INSERT INTO attendance (student_id, attendance_date, check_in, status) "
        "VALUES (%s, %s, %s, 'INCOMPLETE')",
        (sid, now.date(), now.time().replace(microsecond=0)),
    )
    return success_response("Check-in successful.", {"attendance": _clean(_today_row(sid))}, 201)


@attendance_bp.post("/check-out")
@auth_required("STUDENT")
def check_out():
    sid = g.current_user["student_id"]
    row = _today_row(sid)
    if not row or row["check_in"] is None:
        raise APIError("You must check in first.", 409)
    if row["check_out"] is not None:
        raise APIError("You have already checked out today.", 409)

    now = datetime.now()
    worked = (
        now.hour * 3600 + now.minute * 60 + now.second - row["check_in"].total_seconds()
    ) / 3600
    full = current_app.config["FULL_DAY_HOURS"]
    half = current_app.config["HALF_DAY_HOURS"]
    late_cutoff = _cfg_time("LATE_CUTOFF_TIME")
    checked_in_late = (datetime.min + row["check_in"]).time() > late_cutoff

    if worked >= full and not checked_in_late:
        status = "PRESENT"
    elif worked >= half:
        status = "HALF_DAY"
    else:
        status = "ABSENT"

    execute(
        "UPDATE attendance SET check_out = %s, status = %s WHERE id = %s",
        (now.time().replace(microsecond=0), status, row["id"]),
    )
    return success_response("Check-out successful.", {
        "attendance": _clean(_today_row(sid)), "hours_worked": round(worked, 2),
    })


@attendance_bp.get("/today")
@auth_required("STUDENT")
def today_status():
    sid = g.current_user["student_id"]
    now = datetime.now()
    row = _today_row(sid)
    on_leave = _approved_leave_today(sid) is not None
    holiday = off_day_reason(now.date())
    open_window = _cfg_time("COLLEGE_START_TIME") <= now.time() < _cfg_time("ATTENDANCE_CLOSING_TIME")
    return success_response("Today's status.", {
        "attendance": _clean(row),
        "can_check_in": row is None and not on_leave and holiday is None and open_window,
        "can_check_out": row is not None and row["check_in"] is not None and row["check_out"] is None,
        "on_leave": on_leave,
        "holiday": holiday,
    })


@attendance_bp.get("/my")
@auth_required("STUDENT")
def my_history():
    rows = query_all(
        "SELECT * FROM attendance WHERE student_id = %s ORDER BY attendance_date DESC",
        (g.current_user["student_id"],),
    )
    return success_response("Attendance history.", {
        "records": [_clean(r) for r in rows], "count": len(rows),
    })