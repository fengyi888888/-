"""安全与运维用例：限流、角色权限、健康检查。"""

from tests.conftest import auth, login


def test_login_is_rate_limited(client):
    from app import create_app

    client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "email": "alice@campus.edu", "password": "Passw0rd!"},
    )
    statuses = [login(client, password="bad").status_code for _ in range(10)]
    assert statuses == [401] * 10

    blocked = login(client, password="bad")
    assert blocked.status_code == 429
    assert blocked.get_json()["code"] == 42901
    assert "retry_after" in blocked.get_json()["details"]


def test_category_creation_requires_admin(client, user_token):
    payload = {"name": "学习资料"}
    resp = client.post("/api/v1/categories", json=payload, headers=auth(user_token))
    assert resp.status_code == 403


def test_admin_can_create_and_delete_category(client, admin_token):
    created = client.post(
        "/api/v1/categories", json={"name": "学习资料", "sort_order": 2}, headers=auth(admin_token)
    )
    assert created.status_code == 201
    category_id = created.get_json()["data"]["id"]

    listed = client.get("/api/v1/categories").get_json()["data"]
    assert any(c["id"] == category_id for c in listed)

    deleted = client.delete(f"/api/v1/categories/{category_id}", headers=auth(admin_token))
    assert deleted.status_code == 200


def test_category_in_use_cannot_be_deleted(client, admin_token, seed_item):
    resp = client.delete(
        f"/api/v1/categories/{seed_item.category_id}", headers=auth(admin_token)
    )
    assert resp.status_code == 400


def test_healthz_reports_database_up(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["database"] == "up"


def test_unknown_route_returns_unified_error(client):
    resp = client.get("/api/v1/nope")
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["code"] == 40401 and body["data"] is None