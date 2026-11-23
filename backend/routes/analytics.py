from datetime import datetime

from flask import Blueprint, g, request

from auth_utils import auth_required
from db import query_all, query_one
from errors import APIError
from responses import success_response

analytics_bp = Blueprint("analytics", __name__)


def _percentage(present, half, total_working):
    """PRESENT = 1, HALF_DAY = 0.5. SL/CL are excused, not counted in total."""
    if total_working == 0:
        return 0.0
    return round((present + 0.5 * half) * 100.0 / total_working, 2)


def _summary(student_id, start=None, end=None):
    sql = "SELECT status, COUNT(*) AS c FROM attendance WHERE student_id = %s"
    params = [student_id]
    if start:
        sql += " AND attendance_date >= %s"
        params.append(start)
    if end:
        sql += " AND attendance_date <= %s"
        params.append(end)
    sql += " GROUP BY status"
    counts = {r["status"]: r["c"] for r in query_all(sql, tuple(params))}

    present = counts.get("PRESENT", 0)
    half = counts.get("HALF_DAY", 0)
    absent = counts.get("ABSENT", 0)
    incomplete = counts.get("INCOMPLETE", 0)
    sl = counts.get("SL", 0)
    cl = counts.get("CL", 0)
    working = present + half + absent + incomplete  # leave days excluded
    return {
        "present": present, "half_day": half, "absent": absent,
        "incomplete": incomplete, "sick_leave": sl, "casual_leave": cl,
        "working_days": working,
        "attendance_percentage": _percentage(present, half, working),
    }


def _date_args():
    start, end = request.args.get("from"), request.args.get("to")
    for v in (start, end):
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise APIError("Use date format YYYY-MM-DD.", 400)
    return start, end


@analytics_bp.get("/my")
@auth_required("STUDENT")
def my_analytics():
    start, end = _date_args()
    return success_response("Your attendance analytics.", _summary(g.current_user["student_id"], start, end))


@analytics_bp.get("/student/<student_id>")
@auth_required("ADMIN", "FACULTY")
def student_analytics(student_id):
    student = query_one(
        "SELECT student_id, name, department, year, section FROM students WHERE student_id = %s",
        (student_id,),
    )
    user = g.current_user
    if not student or (user["role"] == "FACULTY" and not (
        student["department"] == user["department"]
        and student["year"] == user["year"]
        and student["section"] == user["section"]
    )):
        raise APIError("Student not found.", 404)
    start, end = _date_args()
    return success_response("Student analytics.", {"student": student, **_summary(student_id, start, end)})


@analytics_bp.get("/class")
@auth_required("ADMIN", "FACULTY")
def class_analytics():
    """Per-student summary. Faculty: own class. Admin: all (optional ?department=&year=&section=)."""
    user = g.current_user
    sql = "SELECT student_id, name FROM students"
    conds, params = [], []
    if user["role"] == "FACULTY":
        conds = ["department = %s", "year = %s", "section = %s"]
        params = [user["department"], user["year"], user["section"]]
    else:
        for col in ("department", "year", "section"):
            if request.args.get(col):
                conds.append(f"{col} = %s")  # col from fixed list above
                params.append(request.args[col])
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY student_id"

    start, end = _date_args()
    students = query_all(sql, tuple(params))
    result = [{**s, **_summary(s["student_id"], start, end)} for s in students]
    avg = round(sum(r["attendance_percentage"] for r in result) / len(result), 2) if result else 0.0
    return success_response("Class analytics.", {
        "students": result, "count": len(result), "class_average_percentage": avg,
    })


@analytics_bp.get("/dashboard")
@auth_required("ADMIN", "FACULTY")
def dashboard():
    user = g.current_user
    where, params = "", []
    if user["role"] == "FACULTY":
        where = "WHERE s.department = %s AND s.year = %s AND s.section = %s"
        params = [user["department"], user["year"], user["section"]]
    joiner = where + " AND" if where else "WHERE"

    total = query_one(f"SELECT COUNT(*) AS c FROM students s {where}", tuple(params))["c"]
    today_rows = query_all(
        "SELECT a.status, COUNT(*) AS c FROM attendance a "
        "JOIN students s ON s.student_id = a.student_id "
        f"{joiner} a.attendance_date = CURDATE() GROUP BY a.status",
        tuple(params),
    )
    counts = {r["status"]: r["c"] for r in today_rows}
    pending = query_one(
        "SELECT COUNT(*) AS c FROM leave_requests l JOIN students s ON s.student_id = l.student_id "
        f"{joiner} l.status = 'PENDING'",
        tuple(params),
    )["c"]
    marked = sum(counts.values())

    data = {
        "total_students": total,
        "today": {
            "present": counts.get("PRESENT", 0),
            "half_day": counts.get("HALF_DAY", 0),
            "incomplete": counts.get("INCOMPLETE", 0),
            "absent": counts.get("ABSENT", 0),
            "on_leave": counts.get("SL", 0) + counts.get("CL", 0),
            "not_marked": total - marked,
        },
        "pending_leave_requests": pending,
    }
    if user["role"] == "ADMIN":
        data["total_faculty"] = query_one(
            "SELECT COUNT(*) AS c FROM users WHERE role = 'FACULTY'"
        )["c"]
    return success_response("Dashboard statistics.", data)