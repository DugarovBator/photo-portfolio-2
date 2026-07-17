import io
import sys
from pathlib import Path
from secrets import token_urlsafe

import pytest
from PIL import Image
from PIL.TiffImagePlugin import IFDRational
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402


TEST_PASSWORD = token_urlsafe(24)
TEST_SECRET = token_urlsafe(32)


@pytest.fixture()
def app(tmp_path):
    upload_folder = tmp_path / "uploads"
    staging_folder = upload_folder / ".staging"
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": TEST_SECRET,
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD_HASH": generate_password_hash(TEST_PASSWORD),
            "DATABASE": str(tmp_path / "portfolio.sqlite"),
            "UPLOAD_FOLDER": str(upload_folder),
            "STAGING_FOLDER": str(staging_folder),
            "MAX_CONTENT_LENGTH": 2 * 1024 * 1024,
            "MAX_UPLOAD_MB": 2,
            "LOGIN_MAX_ATTEMPTS": 3,
            "LOGIN_WINDOW_MINUTES": 15,
            "SEED_DATA_PATH": str(Path(__file__).resolve().parents[1] / "data" / "photos.json"),
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf(client):
    response = client.get("/api/csrf")
    assert response.status_code == 200
    return response.get_json()["csrfToken"]


def login(client):
    token = csrf(client)
    response = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": TEST_PASSWORD},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    return response.get_json()["csrfToken"]


def jpeg_with_exif() -> io.BytesIO:
    image = Image.new("RGB", (64, 40), "#7380a5")
    exif = Image.Exif()
    exif[271] = "Fujifilm"
    exif[272] = "X-T5"
    exif[36867] = "2026:07:17 18:22:31"
    exif[34855] = 400
    exif[37386] = IFDRational(50, 1)
    exif[33434] = IFDRational(1, 125)
    exif[33437] = IFDRational(18, 10)
    exif[42036] = "XF 35mm F1.4 R"
    output = io.BytesIO()
    image.save(output, format="JPEG", exif=exif)
    output.seek(0)
    return output


def photo_payload(upload_token):
    return {
        "uploadToken": upload_token,
        "title": "Тестовый кадр",
        "category": "Портреты",
        "description": "Описание",
        "accentColor": "#8095b8",
        "camera": "Fujifilm X-T5",
        "lens": "XF 35mm F1.4 R",
        "capturedAt": "2026-07-17T18:22",
        "iso": "400",
        "focalLength": "50 мм",
        "shutterSpeed": "1/125 с",
        "aperture": "f/1.8",
        "width": 64,
        "height": 40,
    }


def test_public_seed_and_unauthorized_admin(client):
    response = client.get("/api/photos")
    assert response.status_code == 200
    assert len(response.get_json()["photos"]) == 10
    assert client.get("/api/admin/photos").status_code == 401


def test_csrf_and_login(client):
    response = client.post("/api/admin/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 403
    token = csrf(client)
    response = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "wrong"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 401
    response = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": TEST_PASSWORD},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    assert response.get_json()["authenticated"] is True


def test_login_rate_limit(client):
    token = csrf(client)
    for _ in range(3):
        response = client.post(
            "/api/admin/login",
            json={"username": "admin", "password": "wrong"},
            headers={"X-CSRF-Token": token},
        )
        assert response.status_code == 401
    limited = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "wrong"},
        headers={"X-CSRF-Token": token},
    )
    assert limited.status_code == 429


def test_backend_reads_exif_and_strips_metadata(client, app):
    token = login(client)
    response = client.post(
        "/api/admin/photos/inspect",
        data={"image": (jpeg_with_exif(), "capture.jpg")},
        headers={"X-CSRF-Token": token},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    inspected = response.get_json()
    assert inspected["metadata"]["camera"] == "Fujifilm X-T5"
    assert inspected["metadata"]["lens"] == "XF 35mm F1.4 R"
    assert inspected["metadata"]["iso"] == "400"
    assert inspected["metadata"]["width"] == 64
    assert "gps" not in inspected["metadata"]

    created = client.post(
        "/api/admin/photos",
        json=photo_payload(inspected["uploadToken"]),
        headers={"X-CSRF-Token": token},
    )
    assert created.status_code == 201
    photo = created.get_json()["photo"]
    assert photo["image"].startswith("/uploads/")
    saved_path = Path(app.config["UPLOAD_FOLDER"]) / Path(photo["image"]).name
    with Image.open(saved_path) as saved:
        assert saved.getexif() == {}

    public = client.get("/api/photos").get_json()["photos"]
    saved = next(item for item in public if item["id"] == photo["id"])
    assert saved["camera"] == "Fujifilm X-T5"
    assert saved["aperture"] == "f/1.8"


def test_reorder_and_invalid_upload(client):
    token = login(client)
    assert client.put("/api/admin/photos/reorder", json={"ids": [1]}, headers={"X-CSRF-Token": token}).status_code == 400
    response = client.post(
        "/api/admin/photos/inspect",
        data={"image": (io.BytesIO(b"<svg></svg>"), "bad.svg")},
        headers={"X-CSRF-Token": token},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
