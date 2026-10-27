"""商品接口用例：权限、校验、筛选、分页。"""

from tests.conftest import auth


def _create(client, token, **overrides):
    payload = {
        "title": "二手显示器",
        "description": "24 寸，无坏点",
        "price": "399.90",
        "category_id": overrides.pop("category_id", None),
    }
    payload.update(overrides)
    return client.post("/api/v1/items", json=payload, headers=auth(token))


def test_create_item_requires_login(client):
    resp = client.post("/api/v1/items", json={})
    assert resp.status_code == 401


def test_create_item_and_read_detail(client, user_token, category):
    resp = _create(client, user_token, category_id=category.id)
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["price"] == 399.9
    assert data["price_cents"] == 39990
    assert data["status"] == "on_sale"

    detail = client.get(f"/api/v1/items/{data['id']}")
    assert detail.status_code == 200
    assert detail.get_json()["data"]["title"] == "二手显示器"


def test_create_item_rejects_bad_price(client, user_token, category):
    resp = _create(client, user_token, category_id=category.id, price="12.345")
    assert resp.status_code == 400
    assert "price" in resp.get_json()["details"]


def test_create_item_rejects_unknown_category(client, user_token):
    resp = _create(client, user_token, category_id=999)
    assert resp.status_code == 404


def test_detail_increments_view_count(client, seed_item):
    first = client.get(f"/api/v1/items/{seed_item.id}").get_json()["data"]["view_count"]
    second = client.get(f"/api/v1/items/{seed_item.id}").get_json()["data"]["view_count"]
    assert second == first + 1


def test_list_supports_keyword_and_category(client, user_token, category):
    _create(client, user_token, category_id=category.id, title="高数教材 上册")
    _create(client, user_token, category_id=category.id, title="蓝牙耳机")

    resp = client.get("/api/v1/items", query_string={"keyword": "教材"})
    data = resp.get_json()["data"]
    assert data["pagination"]["total"] == 1
    assert data["list"][0]["title"] == "高数教材 上册"

    resp = client.get("/api/v1/items", query_string={"category_id": category.id})
    assert resp.get_json()["data"]["pagination"]["total"] == 2


def test_list_sorts_by_price(client, user_token, category):
    _create(client, user_token, category_id=category.id, title="贵", price="100")
    _create(client, user_token, category_id=category.id, title="便宜", price="10")

    resp = client.get("/api/v1/items", query_string={"sort": "price_asc"})
    prices = [row["price"] for row in resp.get_json()["data"]["list"]]
    assert prices == sorted(prices)


def test_list_pagination_metadata(client, user_token, category):
    for i in range(3):
        _create(client, user_token, category_id=category.id, title=f"商品{i}")
    resp = client.get("/api/v1/items", query_string={"page": 1, "size": 2})
    pagination = resp.get_json()["data"]["pagination"]
    assert pagination == {"page": 1, "size": 2, "total": 3, "pages": 2}


def test_only_owner_can_update_item(client, seed_item, user_token):
    resp = client.patch(
        f"/api/v1/items/{seed_item.id}", json={"title": "改个名字"}, headers=auth(user_token)
    )
    assert resp.status_code == 403


def test_owner_can_update_and_take_off_shelf(client, user_token, category):
    item_id = _create(client, user_token, category_id=category.id).get_json()["data"]["id"]

    resp = client.patch(
        f"/api/v1/items/{item_id}", json={"price": "88.80"}, headers=auth(user_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["price_cents"] == 8880

    resp = client.delete(f"/api/v1/items/{item_id}", headers=auth(user_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "off_shelf"


def test_mine_returns_only_own_items(client, seed_item, user_token, category):
    _create(client, user_token, category_id=category.id)
    resp = client.get("/api/v1/items/mine", headers=auth(user_token))
    data = resp.get_json()["data"]
    assert data["pagination"]["total"] == 1
    assert data["list"][0]["title"] == "二手显示器"