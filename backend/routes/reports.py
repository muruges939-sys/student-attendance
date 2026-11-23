import csv
import io
from datetime import datetime

from flask import Blueprint, Response, g, request

from auth_utils import auth_required
from db import query_all, query_one
from errors import APIError

reports_bp = Blueprint("reports", __name__)


def _csv_response(filename, headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        # prefix risky first characters so Excel does not run them as formulas
        writer.writerow([
            "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v
            for v in row
        ])
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _dates():
    start, end = request.args.get("from"), request.args.get("to")
    if not start or not end:
        raise APIError("Both 'from' and 'to' (YYYY-MM-DD) are required.", 400)
    try:
        s = datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        raise APIError("Use date format YYYY-MM-DD.", 400)
    if e < s:
        raise APIError("'to' cannot be before 'from'.", 400)
    return s, e


def _class_filter():
    """Returns (WHERE fragment, params). Faculty: own class. Admin: optional filters."""
    user = g.current_user
    conds, params = [], []
    if user["role"] == "FACULTY":
        conds = ["s.department = %s", "s.year = %s", "s.section = %s"]
        params = [user["department"], user["year"], user["section"]]
    else:
        for col in ("department", "year", "section"):
            if request.args.get(col):
                conds.append(f"s.{col} = %s")  # col from fixed list
                params.append(request.args[col])
    return conds, params


@reports_bp.get("/attendance.csv")
@auth_required("ADMIN", "FACULTY")
def attendance_report():
    """GET /api/reports/attendance.csv?from=YYYY-MM-DD&to=YYYY-MM-DD"""
    start, end = _dates()
    conds, params = _class_filter()
    conds += ["a.attendance_date BETWEEN %s AND %s"]
    params += [start, end]
    rows = query_all(
        "SELECT s.student_id, s.name, s.department, s.year, s.section, "
        "a.attendance_date, a.check_in, a.check_out, a.status, a.marked_by "
        "FROM attendance a JOIN students s ON s.student_id = a.student_id "
        "WHERE " + " AND ".join(conds) + " ORDER BY a.attendance_date, s.student_id",
        tuple(params),
    )
    return _csv_response(
        f"attendance_{start}_to_{end}.csv",
        ["Student ID", "Name", "Department", "Year", "Section", "Date",
         "Check In", "Check Out", "Status", "Marked By"],
        [[r["student_id"], r["name"], r["department"], r["year"], r["section"],
          str(r["attendance_date"]), r["check_in"] and str(r["check_in"]),
          r["check_out"] and str(r["check_out"]), r["status"], r["marked_by"]] for r in rows],
    )


@reports_bp.get("/summary.csv")
@auth_required("ADMIN", "FACULTY")
def summary_report():
    """Per-student totals and percentage for the date range."""
    start, end = _dates()
    conds, params = _class_filter()
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = query_all(
        "SELECT s.student_id, s.name, "
        "SUM(a.status = 'PRESENT') AS present, SUM(a.status = 'HALF_DAY') AS half_day, "
        "SUM(a.status = 'ABSENT') AS absent, SUM(a.status = 'INCOMPLETE') AS incomplete, "
        "SUM(a.status = 'SL') AS sl, SUM(a.status = 'CL') AS cl "
        "FROM students s LEFT JOIN attendance a "
        "ON a.student_id = s.student_id AND a.attendance_date BETWEEN %s AND %s "
        f"{where} GROUP BY s.student_id, s.name ORDER BY s.student_id",
        (start, end, *params),
    )
    out = []
    for r in rows:
        p, h, ab, inc = (int(r[k] or 0) for k in ("present", "half_day", "absent", "incomplete"))
        working = p + h + ab + inc
        pct = round((p + 0.5 * h) * 100.0 / working, 2) if working else 0.0
        out.append([r["student_id"], r["name"], p, h, ab, inc,
                    int(r["sl"] or 0), int(r["cl"] or 0), working, pct])
    return _csv_response(
        f"summary_{start}_to_{end}.csv",
        ["Student ID", "Name", "Present", "Half Day", "Absent", "Incomplete",
         "SL", "CL", "Working Days", "Attendance %"],
        out,
    )


@reports_bp.get("/leaves.csv")
@auth_required("ADMIN", "FACULTY")
def leaves_report():
    start, end = _dates()
    conds, params = _class_filter()
    conds += ["l.start_date <= %s AND l.end_date >= %s"]
    params += [end, start]
    rows = query_all(
        "SELECT s.student_id, s.name, l.leave_type, l.start_date, l.end_date, "
        "l.status, l.reason, l.reviewed_by, l.remarks "
        "FROM leave_requests l JOIN students s ON s.student_id = l.student_id "
        "WHERE " + " AND ".join(conds) + " ORDER BY l.start_date, s.student_id",
        tuple(params),
    )
    return _csv_response(
        f"leaves_{start}_to_{end}.csv",
        ["Student ID", "Name", "Type", "Start", "End", "Status", "Reason", "Reviewed By", "Remarks"],
        [[r["student_id"], r["name"], r["leave_type"], str(r["start_date"]), str(r["end_date"]),
          r["status"], r["reason"], r["reviewed_by"], r["remarks"]] for r in rows],
    )