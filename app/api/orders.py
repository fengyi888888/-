"""订单接口：下单、支付、确认收货、取消，全部围绕订单状态机。"""

import secrets
from datetime import datetime, timezone

from flask import Blueprint, g, request

from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.extensions import db
from app.models import Item, ItemStatus, Order, OrderStatus
from app.responses import current_page_args, ok, paginated
from app.security import login_required
from app.validators import Validator

bp = Blueprint("orders", __name__, url_prefix="/orders")


def _gen_order_no() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{stamp}{secrets.token_hex(3).upper()}"


def _get_order_or_404(order_id: int) -> Order:
    order = db.session.get(Order, order_id)
    if order is None:
        raise NotFoundError("订单不存在")
    return order


def _ensure_participant(order: Order, user) -> None:
    if user.id not in {order.buyer_id, order.seller_id} and user.role != "admin":
        raise ForbiddenError("无权访问该订单")


@bp.post("")
@login_required
def create_order():
    payload = Validator(request.get_json(silent=True)).positive_int("item_id").check()

    # 行锁：MySQL 下 SELECT ... FOR UPDATE 防止同一商品被并发下单
    item = db.session.execute(
        db.select(Item).where(Item.id == payload["item_id"]).with_for_update()
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("商品不存在")
    if item.seller_id == g.current_user.id:
        raise ForbiddenError("不能购买自己发布的商品")
    if item.status != ItemStatus.ON_SALE:
        raise ConflictError("商品当前不可购买")

    order = Order(
        order_no=_gen_order_no(),
        item_id=item.id,
        buyer_id=g.current_user.id,
        seller_id=item.seller_id,
        price_cents=item.price_cents,
        status=OrderStatus.PENDING,
    )
    item.status = ItemStatus.LOCKED
    db.session.add(order)
    db.session.commit()
    return ok(order.to_dict(), message="下单成功", status=201)


@bp.get("")
@login_required
def list_orders():
    role = request.args.get("role", "buyer")
    if role not in {"buyer", "seller"}:
        raise ValidationError({"role": "必须是 buyer 或 seller"})

    stmt = db.select(Order)
    stmt = stmt.where(Order.buyer_id == g.current_user.id) if role == "buyer" \
        else stmt.where(Order.seller_id == g.current_user.id)

    status = request.args.get("status")
    if status:
        if status not in OrderStatus.ALL:
            raise ValidationError({"status": f"必须是 {sorted(OrderStatus.ALL)} 之一"})
        stmt = stmt.where(Order.status == status)

    stmt = stmt.order_by(Order.id.desc())
    page, size = current_page_args()
    result = db.paginate(stmt, page=page, per_page=size, error_out=False)
    return paginated([o.to_dict() for o in result.items], result.total, page, size)


@bp.get("/<int:order_id>")
@login_required
def order_detail(order_id: int):
    order = _get_order_or_404(order_id)
    _ensure_participant(order, g.current_user)
    return ok(order.to_dict())


@bp.post("/<int:order_id>/pay")
@login_required
def pay_order(order_id: int):
    order = _get_order_or_404(order_id)
    if order.buyer_id != g.current_user.id:
        raise ForbiddenError("只有买家可以支付")
    order.pay()
    db.session.commit()
    return ok(order.to_dict(), message="支付成功")


@bp.post("/<int:order_id>/complete")
@login_required
def complete_order(order_id: int):
    order = _get_order_or_404(order_id)
    if order.buyer_id != g.current_user.id:
        raise ForbiddenError("只有买家可以确认收货")
    order.complete()
    db.session.commit()
    return ok(order.to_dict(), message="交易完成")


@bp.post("/<int:order_id>/cancel")
@login_required
def cancel_order(order_id: int):
    order = _get_order_or_404(order_id)
    _ensure_participant(order, g.current_user)
    order.cancel()
    db.session.commit()
    return ok(order.to_dict(), message="订单已取消")