"""收藏接口：添加、取消、列表（带上商品的精简信息）。"""

from flask import Blueprint, g, request

from app.errors import ConflictError, NotFoundError
from app.extensions import db
from app.models import Favorite, Item
from app.responses import current_page_args, ok, paginated
from app.security import login_required
from app.validators import Validator

bp = Blueprint("favorites", __name__, url_prefix="/favorites")


@bp.get("")
@login_required
def list_favorites():
    page, size = current_page_args()
    stmt = (
        db.select(Favorite)
        .where(Favorite.user_id == g.current_user.id)
        .order_by(Favorite.id.desc())
    )
    result = db.paginate(stmt, page=page, per_page=size, error_out=False)
    items = []
    for fav in result.items:
        item = db.session.get(Item, fav.item_id)
        if item is None:
            continue
        items.append(
            {
                "favorite_id": fav.id,
                "created_at": fav.created_at.isoformat(timespec="seconds"),
                "item": item.to_dict(),
            }
        )
    return paginated(items, result.total, page, size)


@bp.post("")
@login_required
def add_favorite():
    payload = Validator(request.get_json(silent=True)).positive_int("item_id").check()
    if db.session.get(Item, payload["item_id"]) is None:
        raise NotFoundError("商品不存在")
    exists = db.session.execute(
        db.select(Favorite).where(
            Favorite.user_id == g.current_user.id, Favorite.item_id == payload["item_id"]
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("已经收藏过了")
    favorite = Favorite(user_id=g.current_user.id, item_id=payload["item_id"])
    db.session.add(favorite)
    db.session.commit()
    return ok({"id": favorite.id, "item_id": favorite.item_id}, message="收藏成功", status=201)


@bp.delete("/<int:item_id>")
@login_required
def remove_favorite(item_id: int):
    favorite = db.session.execute(
        db.select(Favorite).where(
            Favorite.user_id == g.current_user.id, Favorite.item_id == item_id
        )
    ).scalar_one_or_none()
    if favorite is None:
        raise NotFoundError("尚未收藏该商品")
    db.session.delete(favorite)
    db.session.commit()
    return ok(None, message="已取消收藏")