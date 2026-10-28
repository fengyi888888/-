"""应用工厂：配置、扩展、蓝图、错误处理、日志、CLI 一处装配。"""

import logging
import time
import uuid

from flask import Flask, g, request

from app.api import register_blueprints
from app.config import get_config
from app.errors import register_error_handlers
from app.extensions import db


def create_app(config_name: str | None = None, overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))
    if overrides:
        app.config.update(overrides)

    # 让中文在 JSON 响应里原样输出，而不是 \uXXXX 转义
    app.json.ensure_ascii = False

    _setup_logging(app)
    app.logger.info("database: %s", _mask_uri(app.config["SQLALCHEMY_DATABASE_URI"]))

    db.init_app(app)
    register_blueprints(app)
    register_error_handlers(app)
    _register_hooks(app)

    from app.cli import register_cli

    register_cli(app)
    return app


def _mask_uri(uri: str) -> str:
    """日志里隐藏数据库密码，只保留结构。"""
    if "://" in uri and "@" in uri:
        scheme, rest = uri.split("://", 1)
        credentials, host = rest.split("@", 1)
        user = credentials.split(":", 1)[0]
        return f"{scheme}://{user}:***@{host}"
    return uri


def _setup_logging(app: Flask) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.DEBUG if app.config.get("DEBUG") else logging.INFO)


def _register_hooks(app: Flask) -> None:
    @app.before_request
    def _start_timer():
        g.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
        g.started_at = time.perf_counter()

    @app.after_request
    def _log_request(response):
        cost_ms = (time.perf_counter() - getattr(g, "started_at", time.perf_counter())) * 1000
        app.logger.info(
            "%s %s -> %s %.1fms request_id=%s",
            request.method,
            request.full_path.rstrip("?"),
            response.status_code,
            cost_ms,
            getattr(g, "request_id", "-"),
        )
        response.headers["X-Request-Id"] = getattr(g, "request_id", "-")
        return response