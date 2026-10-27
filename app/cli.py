"""命令行工具：flask init-db / seed / create-admin。"""

import click
from flask import Flask
from flask.cli import with_appcontext

from app.extensions import db
from app.models import Category, Item, ItemStatus, User
from app.security import hash_password

DEFAULT_CATEGORIES = ["教材书籍", "数码电子", "生活用品", "运动器材", "代步工具"]


def register_cli(app: Flask) -> None:
    app.cli.add_command(init_db)
    app.cli.add_command(seed)
    app.cli.add_command(create_admin)


@click.command("init-db")
@with_appcontext
def init_db():
    """建表（开发阶段用，生产建议接入 Alembic 迁移）。"""
    db.create_all()
    click.echo("数据库表已创建")


@click.command("seed")
@with_appcontext
def seed():
    """写入演示数据：分类 + 管理员 + 两个普通用户 + 若干商品。"""
    db.create_all()
    for index, name in enumerate(DEFAULT_CATEGORIES):
        if not db.session.execute(db.select(Category).where(Category.name == name)).scalar_one_or_none():
            db.session.add(Category(name=name, sort_order=index))

    users = {}
    for username, email, role in (
        ("admin", "admin@campus.edu", "admin"),
        ("alice", "alice@campus.edu", "user"),
        ("bob", "bob@campus.edu", "user"),
    ):
        user = db.session.execute(db.select(User).where(User.username == username)).scalar_one_or_none()
        if user is None:
            user = User(
                username=username,
                email=email,
                role=role,
                password_hash=hash_password("Passw0rd!"),
            )
            db.session.add(user)
        users[username] = user
    db.session.commit()

    book = db.session.execute(db.select(Category).where(Category.name == "教材书籍")).scalar_one()
    alice = users["alice"]
    if not db.session.execute(db.select(Item).where(Item.seller_id == alice.id)).scalars().first():
        db.session.add_all(
            [
                Item(
                    title="《数据结构与算法分析》九成新",
                    description="考研用完，无笔记，包邮到宿舍楼下。",
                    price_cents=2800,
                    category_id=book.id,
                    seller_id=alice.id,
                    status=ItemStatus.ON_SALE,
                ),
                Item(
                    title="机械键盘 87 键 红轴",
                    description="换了静音的，这把闲置，手感正常。",
                    price_cents=15900,
                    category_id=book.id,
                    seller_id=alice.id,
                    status=ItemStatus.ON_SALE,
                ),
            ]
        )
    db.session.commit()
    click.echo("演示数据已写入（admin/alice/bob，密码 Passw0rd!）")


@click.command("create-admin")
@click.argument("username")
@click.argument("email")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def create_admin(username: str, email: str, password: str):
    """创建一个管理员账号。"""
    if db.session.execute(db.select(User).where(User.username == username)).scalar_one_or_none():
        raise click.ClickException("用户名已存在")
    db.session.add(
        User(username=username, email=email, role="admin", password_hash=hash_password(password))
    )
    db.session.commit()
    click.echo(f"管理员 {username} 创建成功")