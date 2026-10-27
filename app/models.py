"""数据模型：用户、分类、商品、收藏、订单。

金额统一用「分」存整数，避免浮点误差；订单状态用状态机约束流转。
"""

from datetime import datetime, timezone

from app.errors import ConflictError
from app.extensions import db


def utcnow() -> datetime:
    """统一使用不带时区的 UTC 时间，兼容 SQLite 与 MySQL。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class User(TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="user")
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "sort_order": self.sort_order}


class ItemStatus:
    ON_SALE = "on_sale"
    LOCKED = "locked"
    SOLD = "sold"
    OFF_SHELF = "off_shelf"
    ALL = {ON_SALE, LOCKED, SOLD, OFF_SHELF}


class Item(TimestampMixin, db.Model):
    __tablename__ = "items"
    __table_args__ = (
        db.Index("ix_items_status_created", "status", "created_at"),
        db.Index("ix_items_category_status", "category_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    price_cents = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), nullable=False, default=ItemStatus.ON_SALE)
    view_count = db.Column(db.Integer, nullable=False, default=0)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    category = db.relationship("Category", lazy="joined")
    seller = db.relationship("User", lazy="joined")

    def to_dict(self, *, with_seller: bool = True) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "price": round(self.price_cents / 100, 2),
            "price_cents": self.price_cents,
            "status": self.status,
            "view_count": self.view_count,
            "category": self.category.name if self.category else None,
            "category_id": self.category_id,
            "seller_id": self.seller_id,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }
        if with_seller and self.seller:
            data["seller"] = {"id": self.seller.id, "username": self.seller.username}
        return data


class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (db.UniqueConstraint("user_id", "item_id", name="uq_favorite_user_item"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class OrderStatus:
    PENDING = "pending"
    PAID = "paid"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ALL = {PENDING, PAID, COMPLETED, CANCELLED}


class Order(TimestampMixin, db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    price_cents = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), nullable=False, default=OrderStatus.PENDING)
    paid_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    item = db.relationship("Item", lazy="joined")
    buyer = db.relationship("User", foreign_keys=[buyer_id], lazy="joined")
    seller = db.relationship("User", foreign_keys=[seller_id], lazy="joined")

    # ---- 状态机：pending -> paid -> completed，pending/paid -> cancelled ----
    def pay(self) -> None:
        if self.status != OrderStatus.PENDING:
            raise ConflictError(f"订单当前状态为 {self.status}，不能支付")
        self.status = OrderStatus.PAID
        self.paid_at = utcnow()

    def complete(self) -> None:
        if self.status != OrderStatus.PAID:
            raise ConflictError(f"订单当前状态为 {self.status}，不能确认收货")
        self.status = OrderStatus.COMPLETED
        self.closed_at = utcnow()
        self.item.status = ItemStatus.SOLD

    def cancel(self) -> None:
        if self.status not in {OrderStatus.PENDING, OrderStatus.PAID}:
            raise ConflictError(f"订单当前状态为 {self.status}，不能取消")
        self.status = OrderStatus.CANCELLED
        self.closed_at = utcnow()
        if self.item.status == ItemStatus.LOCKED:
            self.item.status = ItemStatus.ON_SALE

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_no": self.order_no,
            "item_id": self.item_id,
            "item_title": self.item.title if self.item else None,
            "price": round(self.price_cents / 100, 2),
            "status": self.status,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "created_at": self.created_at.isoformat(timespec="seconds"),
            "paid_at": self.paid_at.isoformat(timespec="seconds") if self.paid_at else None,
            "closed_at": self.closed_at.isoformat(timespec="seconds") if self.closed_at else None,
        }