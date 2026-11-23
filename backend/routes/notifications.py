from flask import Blueprint, g, request

from auth_utils import auth_required
from db import execute, query_all, query_one
from errors import APIError
from responses import success_response

notifications_bp = Blueprint("notifications", __name__)

COLUMNS = "id, title, message, type, is_read, created_at"


def _clean(row):
    row["is_read"] = bool(row["is_read"])
    if row.get("created_at") is not None:
        row["created_at"] = str(row["created_at"])
    return row


@notifications_bp.get("")
@auth_required("STUDENT")
def list_notifications():
    sid = g.current_user["student_id"]
    unread_only = request.args.get("unread") == "true"
    sql = f"SELECT {COLUMNS} FROM notifications WHERE student_id = %s"
    if unread_only:
        sql += " AND is_read = 0"
    sql += " ORDER BY created_at DESC, id DESC"
    rows = query_all(sql, (sid,))
    return success_response(
        "Notifications fetched.",
        {"notifications": [_clean(r) for r in rows], "count": len(rows)},
    )


@notifications_bp.get("/unread-count")
@auth_required("STUDENT")
def unread_count():
    row = query_one(
        "SELECT COUNT(*) AS unread FROM notifications WHERE student_id = %s AND is_read = 0",
        (g.current_user["student_id"],),
    )
    return success_response("Unread count.", {"unread": row["unread"]})


@notifications_bp.put("/<int:notification_id>/read")
@auth_required("STUDENT")
def mark_read(notification_id):
    sid = g.current_user["student_id"]
    row = query_one(
        "SELECT id FROM notifications WHERE id = %s AND student_id = %s",
        (notification_id, sid),
    )
    if not row:
        raise APIError("Notification not found.", 404)
    execute("UPDATE notifications SET is_read = 1 WHERE id = %s", (notification_id,))
    return success_response("Notification marked as read.")


@notifications_bp.put("/read-all")
@auth_required("STUDENT")
def mark_all_read():
    execute(
        "UPDATE notifications SET is_read = 1 WHERE student_id = %s AND is_read = 0",
        (g.current_user["student_id"],),
    )
    return success_response("All notifications marked as read.")