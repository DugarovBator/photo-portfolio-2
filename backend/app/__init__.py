from pathlib import Path

from flask import Flask, abort, jsonify, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .db import init_app as init_db_app
from .db import init_db, seed_db
from .routes import api
from .security import validate_csrf


def create_app(test_config=None) -> Flask:
    project_root = Path(__file__).resolve().parents[2]
    frontend_dist = project_root / "frontend" / "dist"
    app = Flask(__name__, static_folder=str(frontend_dist), static_url_path="")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    required = ("SECRET_KEY", "ADMIN_USERNAME", "ADMIN_PASSWORD_HASH")
    missing = [name for name in required if not app.config.get(name)]
    placeholders = [
        name
        for name in required
        if str(app.config.get(name, "")).startswith("replace-with")
    ]
    missing.extend(placeholders)
    if missing:
        raise RuntimeError(
            "Не заданы обязательные переменные окружения или оставлены значения-примеры: "
            + ", ".join(dict.fromkeys(missing))
        )

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["STAGING_FOLDER"]).mkdir(parents=True, exist_ok=True)

    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    init_db_app(app)
    app.before_request(validate_csrf)
    app.register_blueprint(api)
    with app.app_context():
        init_db()
        seed_db()

    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        if ".staging" in Path(filename).parts:
            abort(404)
        response = send_from_directory(app.config["UPLOAD_FOLDER"], filename)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.errorhandler(413)
    def upload_too_large(_error):
        return jsonify(
            {
                "error": f"Файл слишком большой. Максимум {app.config['MAX_UPLOAD_MB']} МБ."
            }
        ), 413

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob: https://images.unsplash.com; "
            "font-src 'self' https://fonts.gstatic.com; style-src 'self' 'unsafe-inline' "
            "https://fonts.googleapis.com; script-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        if response.content_type and response.content_type.startswith("application/json"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str):
        if path == "api" or path.startswith("api/"):
            return jsonify({"error": "API-маршрут не найден."}), 404
        candidate = frontend_dist / path
        if path and candidate.is_file():
            return send_from_directory(frontend_dist, path)
        index = frontend_dist / "index.html"
        if index.is_file():
            return send_from_directory(frontend_dist, "index.html")
        return jsonify({"error": "Frontend ещё не собран. Выполните npm run build."}), 404

    return app
