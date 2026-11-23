from flask import current_app

from db import query_one


def off_day_reason(day):
    """Returns a reason text if `day` is a weekly off or holiday, else None."""
    if day.weekday() in current_app.config["WEEKLY_OFF_DAYS"]:
        return "Weekly off"
    row = query_one("SELECT description FROM holidays WHERE holiday_date = %s", (day,))
    return row["description"] if row else None