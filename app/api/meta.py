"""运维接口：健康检查与接口元信息。"""

from flask import Blueprint, current_app

from app.extensions import db
from app.responses import ok

bp = Blueprint("meta", __name__)


@bp.get("/healthz")
def healthz():
    """探活：数据库不可用时返回 503，供负载均衡/监控使用。"""
    try:
        db.session.execute(db.text("SELECT 1"))
        database = "up"
    except Exception as exc:  # noqa: BLE001 - 探活需要吞掉具体异常
        current_app.logger.error("health check failed: %s", exc)
        database = "down"
    status_code = 200 if database == "up" else 503
    return ok({"service": "campus-service-api", "database": database}, status=status_code)


@bp.get("/meta")
def meta():
    return ok(
        {
            "name": "校园服务 API",
            "version": "1.0.0",
            "docs": "/api/v1/meta",
            "resources": ["auth", "items", "categories", "favorites", "orders"],
        }
    )