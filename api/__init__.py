"""Flask API backed exclusively by versioned MySQL results."""
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from . import db


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(FRONTEND_DIST=str(Path(__file__).resolve().parents[1] / "frontend" / "dist"))
    if config:
        app.config.update(config)

    def error(code, message, status):
        return jsonify(error={"code": code, "message": message}), status

    def query_error():
        if "start" in request.args or "end" in request.args:
            return error("DATE_FILTER_UNSUPPORTED", "当前仅提供全量聚合快照，不支持日期筛选。", 400)
        if request.args:
            return error("UNSUPPORTED_QUERY", "此接口不接受查询参数。", 400)
        return None

    @app.get("/api/health")
    def health():
        try:
            with db.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                run_id = db.active_run(conn)
            return jsonify(status="ok" if run_id else "not_ready", database="ok", ready=bool(run_id), run_id=run_id), 200 if run_id else 503
        except db.DatabaseUnavailable:
            return jsonify(status="unavailable", database="unavailable", ready=False), 503

    def result(section=None):
        invalid = query_error()
        if invalid is not None:
            return invalid
        try:
            snapshot = db.load_snapshot()
        except db.DatabaseUnavailable:
            return error("DATABASE_UNAVAILABLE", "MySQL 不可用或尚未初始化，请检查本地配置并导入结果。", 503)
        except db.NoResults:
            return error("RESULTS_NOT_IMPORTED", "尚未导入分析结果。", 503)
        except db.InvalidStoredResults:
            return error("INVALID_STORED_RESULTS", "数据库快照不完整，请重新导入结果。", 503)
        return jsonify(snapshot if section is None else snapshot[section])

    @app.get("/api/dashboard")
    def dashboard():
        return result()

    @app.get("/api/quality")
    def quality():
        return result("quality")

    @app.get("/api/model")
    def model():
        return result("model")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def frontend(path):
        if path == "api" or path.startswith("api/"):
            return error("NOT_FOUND", "接口不存在。", 404)
        root = Path(app.config["FRONTEND_DIST"]).resolve()
        candidate = (root / path).resolve()
        if not candidate.is_relative_to(root) or "\\" in path or any(part.startswith(".") for part in Path(path).parts):
            return error("NOT_FOUND", "资源不存在。", 404)
        if candidate.is_file():
            return send_from_directory(root, path)
        if Path(path).suffix or path.startswith("assets/"):
            return error("NOT_FOUND", "资源不存在。", 404)
        if not (root / "index.html").is_file():
            return error("FRONTEND_NOT_BUILT", "前端尚未构建。", 404)
        return send_from_directory(root, "index.html")

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return error(exc.name.upper().replace(" ", "_"), exc.description, exc.code)

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app
