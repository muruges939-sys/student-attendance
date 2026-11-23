from datetime import datetime, timedelta

from flask import Blueprint, g, request

from auth_utils import auth_required
from db import execute, get_db, query_all, query_one
from errors import APIError
from responses import success_response

leaves_bp = Blueprint("leaves", __name__)

MAX_LEAVE_DAYS = 30

LEAVE_SELECT = (
    "SELECT l.id, l.student_id, s.name AS student_name, l.leave_type, l.start_date, "
    "l.end_date, l.reason, l.status, l.reviewed_by, l.remarks, l.created_at, l.reviewed_at "
    "FROM leave_requests l JOIN students s ON s.student_id = l.student_id "
)


def _clean(row):
    for key in ("start_date", "end_date", "created_at", "reviewed_at"):
        if row.get(key) is not None:
            row[key] = str(row[key])
    return row


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _get_leave_for_reviewer(leave_id):
    """Admin: any leave. Faculty: only own class students."""
    leave = query_one(
        "SELECT l.*, s.department, s.year, s.section "
        "FROM leave_requests l JOIN students s ON s.student_id = l.student_id "
        "WHERE l.id = %s",
        (leave_id,),
    )
    user = g.current_user
    if not leave:
        raise APIError("Leave request not found.", 404)
    if user["role"] == "FACULTY" and not (
        leave["department"] == user["department"]
        and leave["year"] == user["year"]
        and leave["section"] == user["section"]
    ):
        raise APIError("Leave request not found.", 404)
    return leave


@leaves_bp.post("")
@auth_required("STUDENT")
def apply_leave():
    data = request.get_json(silent=True) or {}
    errors = {}

    leave_type = data.get("leave_type")
    if leave_type not in ("SL", "CL"):
        errors["leave_type"] = "leave_type must be SL or CL."

    reason = data.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        errors["reason"] = "reason is required."

    start = _parse_date(data.get("start_date"))
    end = _parse_date(data.get("end_date"))
    if start is None:
        errors["start_date"] = "Use format YYYY-MM-DD."
    if end is None:
        errors["end_date"] = "Use format YYYY-MM-DD."
    if start and end:
        if end < start:
            errors["end_date"] = "end_date cannot be before start_date."
        elif (end - start).days + 1 > MAX_LEAVE_DAYS:
            errors["end_date"] = f"Leave cannot be longer than {MAX_LEAVE_DAYS} days."
    if errors:
        raise APIError("Validation failed.", 400, errors)

    sid = g.current_user["student_id"]
    overlap = query_one(
        "SELECT id FROM leave_requests WHERE student_id = %s "
        "AND status IN ('PENDING', 'APPROVED') AND start_date <= %s AND end_date >= %s",
        (sid, end, start),
    )
    if overlap:
        raise APIError("You already have a pending or approved leave for these dates.", 409)

    new_id = execute(
        "INSERT INTO leave_requests (student_id, leave_type, start_date, end_date, reason) "
        "VALUES (%s, %s, %s, %s, %s)",
        (sid, leave_type, start, end, reason.strip()),
    )
    leave = query_one(LEAVE_SELECT + "WHERE l.id = %s", (new_id,))
    return success_response("Leave request submitted.", {"leave": _clean(leave)}, 201)


@leaves_bp.get("/my")
@auth_required("STUDENT")
def my_leaves():
    rows = query_all(
        LEAVE_SELECT + "WHERE l.student_id = %s ORDER BY l.created_at DESC",
        (g.current_user["student_id"],),
    )
    return success_response("Your leave requests.", {"leaves": [_clean(r) for r in rows], "count": len(rows)})


@leaves_bp.put("/<int:leave_id>/cancel")
@auth_required("STUDENT")
def cancel_leave(leave_id):
    leave = query_one(
        "SELECT id, status FROM leave_requests WHERE id = %s AND student_id = %s",
        (leave_id, g.current_user["student_id"]),
    )
    if not leave:
        raise APIError("Leave request not found.", 404)
    if leave["status"] != "PENDING":
        raise APIError("Only pending leave requests can be cancelled.", 409)
    execute("UPDATE leave_requests SET status = 'CANCELLED' WHERE id = %s", (leave_id,))
    return success_response("Leave request cancelled.")


@leaves_bp.get("")
@auth_required("ADMIN", "FACULTY")
def list_leaves():
    user = g.current_user
    status = request.args.get("status")
    if status and status not in ("PENDING", "APPROVED", "REJECTED", "CANCELLED"):
        raise APIError("Invalid status filter.", 400)

    sql = LEAVE_SELECT
    conditions, params = [], []
    if user["role"] == "FACULTY":
        conditions.append("s.department = %s AND s.year = %s AND s.section = %s")
        params += [user["department"], user["year"], user["section"]]
    if status:
        conditions.append("l.status = %s")
        params.append(status)
    if conditions:
        sql += "WHERE " + " AND ".join(conditions) + " "
    sql += "ORDER BY l.created_at DESC"

    rows = query_all(sql, tuple(params))
    return success_response("Leave requests.", {"leaves": [_clean(r) for r in rows], "count": len(rows)})


@leaves_bp.put("/<int:leave_id>/review")
@auth_required("ADMIN", "FACULTY")
def review_leave(leave_id):
    data = request.get_json(silent=True) or {}
    decision = data.get("decision")
    remarks = data.get("remarks")

    errors = {}
    if decision not in ("APPROVED", "REJECTED"):
        errors["decision"] = "decision must be APPROVED or REJECTED."
    if remarks is not None and not isinstance(remarks, str):
        errors["remarks"] = "remarks must be text."
    if errors:
        raise APIError("Validation failed.", 400, errors)
    remarks = remarks.strip() if remarks else None

    leave = _get_leave_for_reviewer(leave_id)
    if leave["status"] != "PENDING":
        raise APIError("This leave request is already " + leave["status"].lower() + ".", 409)

    reviewer = g.current_user["name"]
    db = get_db()
    cursor = db.cursor()
    try:
        if decision == "APPROVED":
            cursor.execute(
                "SELECT COUNT(*) FROM attendance WHERE student_id = %s "
                "AND attendance_date BETWEEN %s AND %s "
                "AND status IN ('PRESENT', 'HALF_DAY', 'INCOMPLETE')",
                (leave["student_id"], leave["start_date"], leave["end_date"]),
            )
            if cursor.fetchone()[0] > 0:
                raise APIError(
                    "Cannot approve: student already has attendance on some of these dates.", 409
                )
            day = leave["start_date"]
            while day <= leave["end_date"]:
                cursor.execute(
                    "INSERT INTO attendance (student_id, attendance_date, status, marked_by) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE status = %s, marked_by = %s",
                    (leave["student_id"], day, leave["leave_type"], reviewer,
                     leave["leave_type"], reviewer),
                )
                day += timedelta(days=1)

        cursor.execute(
            "UPDATE leave_requests SET status = %s, reviewed_by = %s, remarks = %s, "
            "reviewed_at = NOW() WHERE id = %s",
            (decision, reviewer, remarks, leave_id),
        )

        word = "approved" if decision == "APPROVED" else "rejected"
        message = f"Your {leave['leave_type']} request ({leave['start_date']} to {leave['end_date']}) was {word}."
        if remarks:
            message += f" Remarks: {remarks}"
        cursor.execute(
            "INSERT INTO notifications (student_id, title, message, type) VALUES (%s, %s, %s, %s)",
            (leave["student_id"], f"Leave {word}", message, f"LEAVE_{decision}"),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()

    updated = query_one(LEAVE_SELECT + "WHERE l.id = %s", (leave_id,))
    return success_response(f"Leave request {decision.lower()}.", {"leave": _clean(updated)})