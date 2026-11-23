from functools import wraps

from flask import current_app, g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from db import query_one
from errors import APIError


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="auth-token")


def create_token(identifier, role):
    """identifier = users.id for ADMIN/FACULTY, students.student_id for STUDENT."""
    return _serializer().dumps({"id": identifier, "role": role})


def _read_token():
    parts = request.headers.get("Authorization", "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise APIError("Missing or invalid Authorization header.", 401)
    try:
        return _serializer().loads(
            parts[1], max_age=current_app.config["TOKEN_MAX_AGE_SECONDS"]
        )
    except SignatureExpired:
        raise APIError("Session expired. Please log in again.", 401)
    except BadSignature:
        raise APIError("Invalid token.", 401)


def _load_user(payload):
    role = payload.get("role")
    user = None
    if role in ("ADMIN", "FACULTY"):
        user = query_one(
            "SELECT id, name, username, role, department, year, section "
            "FROM users WHERE id = %s AND role = %s",
            (payload.get("id"), role),
        )
    elif role == "STUDENT":
        user = query_one(
            "SELECT id, student_id, name, email, department, year, section "
            "FROM students WHERE student_id = %s",
            (payload.get("id"),),
        )
        if user:
            user["role"] = "STUDENT"
    if not user:
        raise APIError("Account no longer exists.", 401)
    return user


def auth_required(*allowed_roles):
    """Usage:
        @auth_required()                  -> any logged-in user
        @auth_required("ADMIN")           -> admins only
        @auth_required("ADMIN", "FACULTY")
    The logged-in user is available as g.current_user."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            g.current_user = _load_user(_read_token())
            if allowed_roles and g.current_user["role"] not in allowed_roles:
                raise APIError("You do not have permission to do this.", 403)
            return func(*args, **kwargs)

        return wrapper

    return decorator