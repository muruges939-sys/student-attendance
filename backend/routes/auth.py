from flask import Blueprint, g, request
from werkzeug.security import check_password_hash

from auth_utils import auth_required, create_token
from db import query_one
from errors import APIError
from responses import success_response
from flask import Blueprint, current_app, g, request
auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")

    errors = {}
    if not isinstance(username, str) or not username.strip():
        errors["username"] = "Username is required."
    if not isinstance(password, str) or not password:
        errors["password"] = "Password is required."
    if errors:
        raise APIError("Validation failed.", 400, errors)

    user = query_one(
        "SELECT id, name, username, password_hash, role, department, year, section "
        "FROM users WHERE username = %s",
        (username.strip(),),
    )
    if not user or not check_password_hash(user["password_hash"], password):
        raise APIError("Invalid username or password.", 401)

    token = create_token(user["id"], user["role"])
    user.pop("password_hash")  # never send the hash to the client

    return success_response(
        "Login successful.",
        {"token": token, "token_type": "Bearer", "user": user},
    )


@auth_bp.get("/me")
@auth_required()
def me():
    return success_response("Current user.", {"user": g.current_user})
@auth_bp.post("/student-dev-login")
def student_dev_login():
    # TESTING ONLY. Turn off with ALLOW_DEV_LOGIN=false in .env
    if not current_app.config["ALLOW_DEV_LOGIN"]:
        raise APIError("Not found.", 404)

    data = request.get_json(silent=True) or {}
    email = data.get("email")
    if not isinstance(email, str) or not email.strip():
        raise APIError("Validation failed.", 400, {"email": "Email is required."})

    student = query_one(
        "SELECT student_id, name, email, department, year, section "
        "FROM students WHERE email = %s",
        (email.strip().lower(),),
    )
    if not student:
        raise APIError("This email is not registered.", 403)

    token = create_token(student["student_id"], "STUDENT")
    student["role"] = "STUDENT"
    return success_response(
        "Login successful.",
        {"token": token, "token_type": "Bearer", "user": student},
    )