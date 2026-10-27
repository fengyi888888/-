"""测试夹具：每个用例一个独立内存库，互不污染。"""

import pytest

from app import create_app
from app.extensions import db
from app.models import Category, Item, ItemStatus, User
from app.ratelimit import reset_buckets
from app.security import hash_password


@pytest.fixture()
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture(autouse=True)
def _clean_rate_limit():
    reset_buckets()
    yield
    reset_buckets()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, username="alice", email="alice@campus.edu", password="Passw0rd!"):
    return client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def login(client, account="alice", password="Passw0rd!"):
    return client.post("/api/v1/auth/login", json={"account": account, "password": password})


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_token(client):
    response = register(client)
    return response.get_json()["data"]["access_token"]


@pytest.fixture()
def second_token(client):
    response = register(client, username="bob", email="bob@campus.edu")
    return response.get_json()["data"]["access_token"]


@pytest.fixture()
def admin_token(app):
    user = User(
        username="root",
        email="root@campus.edu",
        role="admin",
        password_hash=hash_password("Passw0rd!"),
    )
    db.session.add(user)
    db.session.commit()
    from app.security import create_token

    with app.app_context():
        return create_token(user.id, "access")


@pytest.fixture()
def category(app):
    category = Category(name="教材书籍", sort_order=1)
    db.session.add(category)
    db.session.commit()
    return category


@pytest.fixture()
def seed_item(app, category):
    seller = User(
        username="seller",
        email="seller@campus.edu",
        password_hash=hash_password("Passw0rd!"),
    )
    db.session.add(seller)
    db.session.commit()
    item = Item(
        title="数据结构教材",
        description="九成新",
        price_cents=2800,
        category_id=category.id,
        seller_id=seller.id,
        status=ItemStatus.ON_SALE,
    )
    db.session.add(item)
    db.session.commit()
    return item