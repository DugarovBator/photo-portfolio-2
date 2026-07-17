import re
import time
from pathlib import Path
from secrets import token_urlsafe

from flask import Blueprint, current_app, jsonify, request, send_from_directory, session

from .db import PHOTO_COLUMNS, get_db
from .media import HEX_COLOR, MediaValidationError, inspect_and_sanitize
from .security import (
    admin_required,
    clear_login_failures,
    client_ip,
    credentials_are_valid,
    csrf_token,
    login_is_limited,
    record_login_failure,
)


api = Blueprint("api", __name__, url_prefix="/api")

CATEGORIES = {"Портреты", "Улица", "Природа", "Архитектура", "Ночная съёмка"}
TECH_FIELDS = {
    "camera": 160,
    "lens": 200,
    "capturedAt": 40,
    "iso": 32,
    "focalLength": 40,
    "shutterSpeed": 40,
    "aperture": 32,
}


def _photo_dict(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "description": row["description"],
        "image": row["image"],
        "accentColor": row["accent_color"],
        "sortOrder": row["sort_order"],
        "camera": row["camera"],
        "lens": row["lens"],
        "capturedAt": row["captured_at"],
        "iso": row["iso"],
        "focalLength": row["focal_length"],
        "shutterSpeed": row["shutter_speed"],
        "aperture": row["aperture"],
        "width": row["width"],
        "height": row["height"],
    }


def _text(value, limit: int, required: bool = False) -> str | None:
    text = "" if value is None else str(value).replace("\x00", "").strip()
    if required and not text:
        raise ValueError("Заполните обязательные поля.")
    if len(text) > limit:
        raise ValueError("Одно из полей превышает допустимую длину.")
    return text or None


def _positive_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Размеры изображения должны быть числами.") from error
    if number <= 0 or number > 100_000:
        raise ValueError("Некорректный размер изображения.")
    return number


def _validate_photo(data: dict) -> dict:
    title = _text(data.get("title"), 160, required=True)
    description = _text(data.get("description"), 1600) or ""
    category = _text(data.get("category"), 64, required=True)
    if category not in CATEGORIES:
        raise ValueError("Выберите допустимую категорию.")
    accent_color = str(data.get("accentColor", "#7788ff")).strip()
    if not HEX_COLOR.fullmatch(accent_color):
        raise ValueError("Акцентный цвет должен быть в формате #RRGGBB.")

    values = {
        "title": title,
        "description": description,
        "category": category,
        "accent_color": accent_color.lower(),
        "width": _positive_int(data.get("width")),
        "height": _positive_int(data.get("height")),
    }
    for api_name, limit in TECH_FIELDS.items():
        values[api_name] = _text(data.get(api_name), limit)
    return values


def _cleanup_staging() -> None:
    db = get_db()
    cutoff = int(time.time()) - 3600
    rows = db.execute(
        "SELECT filename FROM staged_uploads WHERE created_at < ?", (cutoff,)
    ).fetchall()
    staging = Path(current_app.config["STAGING_FOLDER"])
    for row in rows:
        (staging / row["filename"]).unlink(missing_ok=True)
    db.execute("DELETE FROM staged_uploads WHERE created_at < ?", (cutoff,))
    db.commit()


def _consume_staged_upload(token: str) -> str:
    db = get_db()
    row = db.execute(
        "SELECT * FROM staged_uploads WHERE token = ? AND session_id = ?",
        (token, session.get("admin_session_id", "")),
    ).fetchone()
    if row is None:
        raise ValueError("Загрузка устарела. Выберите файл ещё раз.")

    source = Path(current_app.config["STAGING_FOLDER"]) / row["filename"]
    destination = Path(current_app.config["UPLOAD_FOLDER"]) / row["filename"]
    if not source.is_file():
        raise ValueError("Временный файл не найден. Выберите его ещё раз.")
    source.replace(destination)
    db.execute("DELETE FROM staged_uploads WHERE token = ?", (token,))
    db.commit()
    return f"/uploads/{row['filename']}"


def _remove_local_image(image_url: str) -> None:
    if not image_url.startswith("/uploads/"):
        return
    filename = Path(image_url).name
    if not re.fullmatch(r"[0-9a-f]{32}\.(jpg|png|webp)", filename):
        return
    (Path(current_app.config["UPLOAD_FOLDER"]) / filename).unlink(missing_ok=True)


@api.get("/csrf")
def get_csrf():
    return jsonify({"csrfToken": csrf_token()})


@api.get("/photos")
def public_photos():
    rows = get_db().execute(
        f"SELECT {PHOTO_COLUMNS} FROM photos ORDER BY sort_order, id"
    ).fetchall()
    return jsonify({"photos": [_photo_dict(row) for row in rows]})


@api.get("/admin/session")
def admin_session():
    return jsonify(
        {
            "authenticated": bool(session.get("admin_authenticated")),
            "username": current_app.config["ADMIN_USERNAME"]
            if session.get("admin_authenticated")
            else None,
        }
    )


@api.post("/admin/login")
def admin_login():
    ip_address = client_ip()
    limited, window = login_is_limited(ip_address)
    if limited:
        response = jsonify({"error": "Слишком много попыток. Попробуйте позже."})
        response.status_code = 429
        response.headers["Retry-After"] = str(window)
        return response

    data = request.get_json(silent=True) or {}
    username = str(data.get("username", ""))[:160]
    password = str(data.get("password", ""))[:512]
    if not credentials_are_valid(username, password):
        record_login_failure(ip_address)
        return jsonify({"error": "Неверный логин или пароль."}), 401

    clear_login_failures(ip_address)
    session.clear()
    session.permanent = True
    session["admin_authenticated"] = True
    session["admin_session_id"] = token_urlsafe(24)
    return jsonify(
        {
            "authenticated": True,
            "username": current_app.config["ADMIN_USERNAME"],
            "csrfToken": csrf_token(),
        }
    )


@api.post("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return jsonify({"ok": True})


@api.get("/admin/photos")
@admin_required
def admin_photos():
    return public_photos()


@api.post("/admin/photos/inspect")
@admin_required
def inspect_photo():
    _cleanup_staging()
    upload = request.files.get("image")
    try:
        result = inspect_and_sanitize(upload, current_app.config["STAGING_FOLDER"])
    except MediaValidationError as error:
        return jsonify({"error": str(error)}), 400

    db = get_db()
    db.execute(
        """
        INSERT INTO staged_uploads (
            token, session_id, filename, original_filename,
            mime_type, byte_size, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result["token"],
            session["admin_session_id"],
            result["filename"],
            Path(upload.filename).name[:255],
            result["mimeType"],
            result["byteSize"],
            int(time.time()),
        ),
    )
    db.commit()
    return jsonify(
        {
            "uploadToken": result["token"],
            "previewUrl": f"/api/admin/staged/{result['token']}",
            "metadata": result["metadata"],
        }
    )


@api.get("/admin/staged/<token>")
@admin_required
def staged_preview(token: str):
    row = get_db().execute(
        "SELECT filename FROM staged_uploads WHERE token = ? AND session_id = ?",
        (token, session.get("admin_session_id", "")),
    ).fetchone()
    if row is None:
        return jsonify({"error": "Файл не найден."}), 404
    response = send_from_directory(current_app.config["STAGING_FOLDER"], row["filename"])
    response.headers["Cache-Control"] = "no-store"
    return response


@api.post("/admin/photos")
@admin_required
def create_photo():
    data = request.get_json(silent=True) or {}
    try:
        values = _validate_photo(data)
        upload_token = _text(data.get("uploadToken"), 128, required=True)
        image_url = _consume_staged_upload(upload_token)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    db = get_db()
    sort_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM photos"
    ).fetchone()[0]
    cursor = db.execute(
        """
        INSERT INTO photos (
            title, category, description, image, accent_color, sort_order,
            camera, lens, captured_at, iso, focal_length, shutter_speed,
            aperture, width, height, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            values["title"], values["category"], values["description"], image_url,
            values["accent_color"], sort_order, values["camera"], values["lens"],
            values["capturedAt"], values["iso"], values["focalLength"],
            values["shutterSpeed"], values["aperture"], values["width"], values["height"],
        ),
    )
    db.commit()
    row = db.execute(
        f"SELECT {PHOTO_COLUMNS} FROM photos WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return jsonify({"photo": _photo_dict(row)}), 201


@api.put("/admin/photos/<int:photo_id>")
@admin_required
def update_photo(photo_id: int):
    db = get_db()
    existing = db.execute(
        f"SELECT {PHOTO_COLUMNS} FROM photos WHERE id = ?", (photo_id,)
    ).fetchone()
    if existing is None:
        return jsonify({"error": "Фотография не найдена."}), 404

    data = request.get_json(silent=True) or {}
    try:
        values = _validate_photo(data)
        image_url = existing["image"]
        upload_token = _text(data.get("uploadToken"), 128)
        if upload_token:
            image_url = _consume_staged_upload(upload_token)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    db.execute(
        """
        UPDATE photos SET
            title = ?, category = ?, description = ?, image = ?, accent_color = ?,
            camera = ?, lens = ?, captured_at = ?, iso = ?, focal_length = ?,
            shutter_speed = ?, aperture = ?, width = ?, height = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            values["title"], values["category"], values["description"], image_url,
            values["accent_color"], values["camera"], values["lens"],
            values["capturedAt"], values["iso"], values["focalLength"],
            values["shutterSpeed"], values["aperture"], values["width"],
            values["height"], photo_id,
        ),
    )
    db.commit()
    if image_url != existing["image"]:
        _remove_local_image(existing["image"])
    row = db.execute(
        f"SELECT {PHOTO_COLUMNS} FROM photos WHERE id = ?", (photo_id,)
    ).fetchone()
    return jsonify({"photo": _photo_dict(row)})


@api.delete("/admin/photos/<int:photo_id>")
@admin_required
def delete_photo(photo_id: int):
    db = get_db()
    existing = db.execute(
        "SELECT image FROM photos WHERE id = ?", (photo_id,)
    ).fetchone()
    if existing is None:
        return jsonify({"error": "Фотография не найдена."}), 404
    db.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    db.commit()
    _remove_local_image(existing["image"])
    return jsonify({"ok": True})


@api.put("/admin/photos/reorder")
@admin_required
def reorder_photos():
    data = request.get_json(silent=True) or {}
    photo_ids = data.get("ids")
    if not isinstance(photo_ids, list) or not photo_ids:
        return jsonify({"error": "Передайте новый порядок фотографий."}), 400
    try:
        normalized = [int(photo_id) for photo_id in photo_ids]
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректный список фотографий."}), 400
    if len(normalized) != len(set(normalized)):
        return jsonify({"error": "В порядке есть повторяющиеся фотографии."}), 400

    db = get_db()
    existing_ids = {row[0] for row in db.execute("SELECT id FROM photos").fetchall()}
    if set(normalized) != existing_ids:
        return jsonify({"error": "Список должен содержать все фотографии."}), 400
    db.executemany(
        "UPDATE photos SET sort_order = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [(index, photo_id) for index, photo_id in enumerate(normalized)],
    )
    db.commit()
    return jsonify({"ok": True})
