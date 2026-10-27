"""分类接口：公开查询，管理员维护。"""

from flask import Blueprint, request

from app.errors import ConflictError, NotFoundError, ValidationError
from app.extensions import db
from app.models import Category, Item
from app.responses import ok
from app.security import admin_required
from app.validators import Validator

bp = Blueprint("categories", __name__, url_prefix="/categories")


@bp.get("")
def list_categories():
    rows = db.session.execute(
        db.select(Category).order_by(Category.sort_order.asc(), Category.id.asc())
    ).scalars().all()
    return ok([c.to_dict() for c in rows])


@bp.post("")
@admin_required
def create_category():
    payload = Validator(request.get_json(silent=True)) \
        .required_str("name", min_len=1, max_len=32) \
        .optional_int("sort_order") \
        .check()
    if db.session.execute(db.select(Category).where(Category.name == payload["name"])).scalar_one_or_none():
        raise ConflictError("分类已存在")
    category = Category(name=payload["name"], sort_order=payload.get("sort_order", 0) or 0)
    db.session.add(category)
    db.session.commit()
    return ok(category.to_dict(), message="创建成功", status=201)


@bp.patch("/<int:category_id>")
@admin_required
def update_category(category_id: int):
    category = db.session.get(Category, category_id)
    if category is None:
        raise NotFoundError("分类不存在")
    payload = request.get_json(silent=True) or {}
    if "name" in payload:
        Validator(payload).required_str("name", min_len=1, max_len=32).check()
        category.name = payload["name"]
    if "sort_order" in payload:
        Validator(payload).optional_int("sort_order").check()
        category.sort_order = payload["sort_order"] or 0
    db.session.commit()
    return ok(category.to_dict(), message="更新成功")


@bp.delete("/<int:category_id>")
@admin_required
def delete_category(category_id: int):
    category = db.session.get(Category, category_id)
    if category is None:
        raise NotFoundError("分类不存在")
    used = db.session.execute(
        db.select(db.func.count()).select_from(Item).where(Item.category_id == category_id)
    ).scalar_one()
    if used:
        raise ValidationError({"category_id": f"该分类下还有 {used} 件商品，不能删除"})
    db.session.delete(category)
    db.session.commit()
    return ok(None, message="删除成功")