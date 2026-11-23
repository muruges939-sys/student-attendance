import mysql.connector
from flask import current_app, g


def get_db():
    """Open a MySQL connection for the current request (reused within it)."""
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=current_app.config["DB_HOST"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
            database=current_app.config["DB_NAME"],
            port=current_app.config["DB_PORT"],
            charset="utf8mb4",
        )
    return g.db


def close_db(error=None):
    """Runs automatically at the end of every request."""
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def query_all(sql, params=None):
    """SELECT that returns a list of dictionaries."""
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    finally:
        cursor.close()


def query_one(sql, params=None):
    """SELECT that returns one dictionary, or None if nothing matches."""
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchone()
    finally:
        cursor.close()


def execute(sql, params=None):
    """INSERT / UPDATE / DELETE. Commits on success, rolls back on error.
    Returns the new row id (for INSERT)."""
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(sql, params or ())
        db.commit()
        return cursor.lastrowid
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()