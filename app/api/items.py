"""商品接口：发布、检索（分页/筛选/排序）、详情、编辑、下架。"""

from decimal import Decimal, InvalidOperation

from flask import Blueprint, g, request

from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.extensions import db
from app.models import Category, Item, ItemStatus
from app.responses import current_page_args, ok, paginated
from app.security import login_required, optional_login
from app.validators import Validator

bp = Blueprint("items", __name__, url_prefix="/items")

SORT_OPTIONS = {
    "latest": (Item.created_at.desc(),),
    "price_asc": (Item.price_cents.asc(),),
    "price_desc": (Item.price_cents.desc(),),
    "popular": (Item.view_count.desc(),),
}


def _parse_price_cents(
    payload: dict, field: str = "price", required: bool = True, allow_zero: bool = False
):
    """把「元」价格转成整数分，最多两位小数，不接受科学计数法。"""
    raw = payload.get(field)
    if raw is None:
        if required:
            raise ValidationError({field: "不能为空"})
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise ValidationError({field: "必须是数字"}) from None
    if value <= 0 and not (allow_zero and value == 0):
        raise ValidationError({field: "必须大于 0"})
    if value > Decimal("99999.99"):
        raise ValidationError({field: "不能超过 99999.99"})
    if -value.as_tuple().exponent > 2:
        raise ValidationError({field: "最多保留两位小数"})
    return int(value * 100)


def _get_item_or_404(item_id: int) -> Item:
    item = db.session.get(Item, item_id)
    if item is None:
        raise NotFoundError("商品不存在")
    return item


def _ensure_owner(item: Item, user) -> None:
    if item.seller_id != user.id and user.role != "admin":
        raise ForbiddenError("只能操作自己发布的商品")


@bp.get("")
def list_items():
    stmt = db.select(Item)
    status = request.args.get("status", ItemStatus.ON_SALE)
    if status != "all":
        if status not in ItemStatus.ALL:
            raise ValidationError({"status": f"必须是 {sorted(ItemStatus.ALL)} 之一"})
        stmt = stmt.where(Item.status == status)

    keyword = (request.args.get("keyword") or "").strip()
    if keyword:
        stmt = stmt.where(Item.title.like(f"%{keyword}%"))

    category_id = request.args.get("category_id")
    if category_id:
        try:
            stmt = stmt.where(Item.category_id == int(category_id))
        except ValueError:
            raise ValidationError({"category_id": "必须是整数"}) from None

    min_price = request.args.get("min_price")
    if min_price:
        stmt = stmt.where(Item.price_cents >= _parse_price_cents({"min": min_price}, "min", allow_zero=True))
    max_price = request.args.get("max_price")
    if max_price:
        stmt = stmt.where(Item.price_cents <= _parse_price_cents({"max": max_price}, "max", allow_zero=True))

    sort = request.args.get("sort", "latest")
    if sort not in SORT_OPTIONS:
        raise ValidationError({"sort": f"必须是 {sorted(SORT_OPTIONS)} 之一"})
    stmt = stmt.order_by(*SORT_OPTIONS[sort], Item.id.desc())

    page, size = current_page_args()
    result = db.paginate(stmt, page=page, per_page=size, error_out=False)
    return paginated([i.to_dict() for i in result.items], result.total, page, size)


@bp.get("/mine")
@login_required
def my_items():
    page, size = current_page_args()
    stmt = db.select(Item).where(Item.seller_id == g.current_user.id).order_by(Item.id.desc())
    result = db.paginate(stmt, page=page, per_page=size, error_out=False)
    return paginated([i.to_dict(with_seller=False) for i in result.items], result.total, page, size)


@bp.get("/<int:item_id>")
@optional_login
def item_detail(item_id: int):
    item = _get_item_or_404(item_id)
    item.view_count += 1
    db.session.commit()
    return ok(item.to_dict())


@bp.post("")
@login_required
def create_item():
    payload = Validator(request.get_json(silent=True)) \
        .required_str("title", min_len=2, max_len=120) \
        .required_str("description", max_len=2000) \
        .positive_int("category_id") \
        .check()
    price_cents = _parse_price_cents(payload)

    category = db.session.get(Category, payload["category_id"])
    if category is None:
        raise NotFoundError("分类不存在")

    item = Item(
        title=payload["title"],
        description=payload["description"],
        price_cents=price_cents,
        category_id=category.id,
        seller_id=g.current_user.id,
        status=ItemStatus.ON_SALE,
    )
    db.session.add(item)
    db.session.commit()
    return ok(item.to_dict(), message="发布成功", status=201)


@bp.patch("/<int:item_id>")
@login_required
def update_item(item_id: int):
    item = _get_item_or_404(item_id)
    _ensure_owner(item, g.current_user)
    if item.status == ItemStatus.LOCKED:
        raise ForbiddenError("交易中的商品不能修改")

    payload = request.get_json(silent=True) or {}
    if "title" in payload:
        Validator(payload).required_str("title", min_len=2, max_len=120).check()
        item.title = payload["title"].strip()
    if "description" in payload:
        Validator(payload).required_str("description", max_len=2000).check()
        item.description = payload["description"].strip()
    if "price" in payload:
        item.price_cents = _parse_price_cents(payload)
    if "category_id" in payload:
        Validator(payload).positive_int("category_id").check()
        if db.session.get(Category, payload["category_id"]) is None:
            raise NotFoundError("分类不存在")
        item.category_id = payload["category_id"]
    if "status" in payload:
        if payload["status"] not in {ItemStatus.ON_SALE, ItemStatus.OFF_SHELF}:
            raise ValidationError({"status": "只能切换为 on_sale 或 off_shelf"})
        item.status = payload["status"]

    db.session.commit()
    return ok(item.to_dict(), message="更新成功")


@bp.delete("/<int:item_id>")
@login_required
def off_shelf_item(item_id: int):
    item = _get_item_or_404(item_id)
    _ensure_owner(item, g.current_user)
    if item.status == ItemStatus.LOCKED:
        raise ForbiddenError("交易中的商品不能下架")
    item.status = ItemStatus.OFF_SHELF
    db.session.commit()
    return ok(item.to_dict(), message="已下架")