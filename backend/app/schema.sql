PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    image TEXT NOT NULL,
    accent_color TEXT NOT NULL DEFAULT '#7788ff',
    sort_order INTEGER NOT NULL DEFAULT 0,
    camera TEXT,
    lens TEXT,
    captured_at TEXT,
    iso TEXT,
    focal_length TEXT,
    shutter_speed TEXT,
    aperture TEXT,
    width INTEGER,
    height INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS photos_sort_order_idx ON photos(sort_order, id);

CREATE TABLE IF NOT EXISTS staged_uploads (
    token TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS staged_uploads_created_at_idx
ON staged_uploads(created_at);

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_address TEXT NOT NULL,
    attempted_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS login_attempts_ip_time_idx
ON login_attempts(ip_address, attempted_at);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
