import hmac
import time
from functools import wraps
from secrets import token_urlsafe

from flask import current_app, jsonify, request, session
from werkzeug.security import check_password_hash

from .db import get_db


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf():
    if request.method not in UNSAFE_METHODS or not request.path.startswith("/api/"):
        return None
    expected = session.get("csrf_token", "")
    provided = request.headers.get("X-CSRF-Token", "")
    if not expected or not provided or not hmac.compare_digest(expected, provided):
        return jsonify({"error": "Сессия формы устарела. Обновите страницу."}), 403
    return None


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return jsonify({"error": "Требуется авторизация."}), 401
        return view(*args, **kwargs)

    return wrapped


def client_ip() -> str:
    return request.remote_addr or "unknown"


def login_is_limited(ip_address: str) -> tuple[bool, int]:
    db = get_db()
    now = int(time.time())
    window = current_app.config["LOGIN_WINDOW_MINUTES"] * 60
    cutoff = now - window
    db.execute("DELETE FROM login_attempts WHERE attempted_at < ?", (cutoff,))
    count = db.execute(
        "SELECT COUNT(*) FROM login_attempts WHERE ip_address = ? AND attempted_at >= ?",
        (ip_address, cutoff),
    ).fetchone()[0]
    db.commit()
    return count >= current_app.config["LOGIN_MAX_ATTEMPTS"], window


def record_login_failure(ip_address: str) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO login_attempts (ip_address, attempted_at) VALUES (?, ?)",
        (ip_address, int(time.time())),
    )
    db.commit()


def clear_login_failures(ip_address: str) -> None:
    db = get_db()
    db.execute("DELETE FROM login_attempts WHERE ip_address = ?", (ip_address,))
    db.commit()


def credentials_are_valid(username: str, password: str) -> bool:
    expected_username = current_app.config["ADMIN_USERNAME"]
    password_hash = current_app.config["ADMIN_PASSWORD_HASH"]
    username_matches = hmac.compare_digest(username, expected_username)
    try:
        password_matches = check_password_hash(password_hash, password)
    except (ValueError, TypeError):
        password_matches = False
    return username_matches and password_matches

