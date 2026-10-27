"""认证与令牌相关用例。"""

from tests.conftest import auth, login, register


def test_register_returns_token_and_user(client):
    resp = register(client)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["code"] == 0
    assert body["data"]["user"]["username"] == "alice"
    assert body["data"]["access_token"]


def test_register_rejects_duplicate_username(client):
    register(client)
    resp = register(client, email="other@campus.edu")
    assert resp.status_code == 409
    assert resp.get_json()["code"] == 40901


def test_register_rejects_short_password(client):
    resp = register(client, password="123")
    assert resp.status_code == 400
    assert "password" in resp.get_json()["details"]


def test_register_rejects_bad_email(client):
    resp = register(client, email="not-an-email")
    assert resp.status_code == 400
    assert "email" in resp.get_json()["details"]


def test_login_success_and_me(client):
    register(client)
    resp = login(client)
    assert resp.status_code == 200
    token = resp.get_json()["data"]["access_token"]

    me = client.get("/api/v1/auth/me", headers=auth(token))
    assert me.status_code == 200
    assert me.get_json()["data"]["username"] == "alice"


def test_login_wrong_password(client):
    register(client)
    resp = login(client, password="WrongPass1")
    assert resp.status_code == 401
    assert resp.get_json()["code"] == 40101


def test_me_without_token_is_401(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token_is_401(client):
    resp = client.get("/api/v1/auth/me", headers=auth("not.a.jwt"))
    assert resp.status_code == 401


def test_refresh_issues_new_access_token(client):
    register(client)
    refresh_token = login(client).get_json()["data"]["refresh_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    new_access = resp.get_json()["data"]["access_token"]
    assert client.get("/api/v1/auth/me", headers=auth(new_access)).status_code == 200


def test_access_token_cannot_be_used_as_refresh(client):
    register(client)
    access = login(client).get_json()["data"]["access_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401