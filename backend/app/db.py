import json
import sqlite3
from pathlib import Path

from flask import current_app, g


PHOTO_COLUMNS = (
    "id, title, category, description, image, accent_color, sort_order, "
    "camera, lens, captured_at, iso, focal_length, shutter_speed, aperture, "
    "width, height, created_at, updated_at"
)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        database_path = Path(current_app.config["DATABASE"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        g.db = connection
    return g.db


def close_db(_error=None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    db = get_db()
    schema_path = Path(__file__).with_name("schema.sql")
    db.executescript(schema_path.read_text(encoding="utf-8"))
    db.commit()


def seed_db() -> None:
    db = get_db()
    already_seeded = db.execute(
        "SELECT value FROM app_meta WHERE key = 'seeded'"
    ).fetchone()
    if already_seeded is not None:
        return

    if db.execute("SELECT COUNT(*) FROM photos").fetchone()[0] > 0:
        db.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('seeded', '1')"
        )
        db.commit()
        return

    seed_path = Path(current_app.config["SEED_DATA_PATH"])
    photos = json.loads(seed_path.read_text(encoding="utf-8"))
    for index, photo in enumerate(photos):
        db.execute(
            """
            INSERT OR IGNORE INTO photos (
                id, title, category, description, image, accent_color,
                sort_order, camera, lens, captured_at, iso, focal_length,
                shutter_speed, aperture, width, height
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                photo.get("id"), photo["title"], photo["category"],
                photo.get("description", ""), photo["image"],
                photo.get("accentColor", "#7788ff"), photo.get("sortOrder", index),
                photo.get("camera"), photo.get("lens"), photo.get("capturedAt"),
                photo.get("iso"), photo.get("focalLength"),
                photo.get("shutterSpeed"), photo.get("aperture"),
                photo.get("width"), photo.get("height"),
            ),
        )
    db.execute(
        "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('seeded', '1')"
    )
    db.commit()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
