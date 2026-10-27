"""蓝图注册：所有业务接口统一挂在 /api/v1 下。"""

from flask import Flask

from app.api import auth, categories, favorites, items, meta, orders

API_PREFIX = "/api/v1"


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(auth.bp, url_prefix=f"{API_PREFIX}/auth")
    app.register_blueprint(items.bp, url_prefix=f"{API_PREFIX}/items")
    app.register_blueprint(categories.bp, url_prefix=f"{API_PREFIX}/categories")
    app.register_blueprint(favorites.bp, url_prefix=f"{API_PREFIX}/favorites")
    app.register_blueprint(orders.bp, url_prefix=f"{API_PREFIX}/orders")
    # 运维接口同时暴露在根路径，方便负载均衡直接探活
    app.register_blueprint(meta.bp)
    app.register_blueprint(meta.bp, url_prefix=API_PREFIX, name="meta_v1")