"""订单状态机与权限用例。"""

from tests.conftest import auth


def _publish(client, token, category_id, title="健身哑铃"):
    return client.post(
        "/api/v1/items",
        json={"title": title, "description": "自取", "price": "59.00", "category_id": category_id},
        headers=auth(token),
    ).get_json()["data"]["id"]


def _buy(client, token, item_id):
    return client.post("/api/v1/orders", json={"item_id": item_id}, headers=auth(token))


def test_cannot_buy_own_item(client, user_token, category):
    item_id = _publish(client, user_token, category.id)
    resp = _buy(client, user_token, item_id)
    assert resp.status_code == 403


def test_buy_locks_item_and_blocks_second_buyer(client, user_token, second_token, category):
    item_id = _publish(client, user_token, category.id)

    first = _buy(client, second_token, item_id)
    assert first.status_code == 201
    assert first.get_json()["data"]["status"] == "pending"

    item = client.get(f"/api/v1/items/{item_id}").get_json()["data"]
    assert item["status"] == "locked"

    # 另一个买家再下单应冲突
    third = client.post(
        "/api/v1/auth/register",
        json={"username": "carol", "email": "carol@campus.edu", "password": "Passw0rd!"},
    ).get_json()["data"]["access_token"]
    resp = _buy(client, third, item_id)
    assert resp.status_code == 409


def test_full_lifecycle_pay_and_complete(client, user_token, second_token, category):
    item_id = _publish(client, user_token, category.id)
    order = _buy(client, second_token, item_id).get_json()["data"]

    paid = client.post(f"/api/v1/orders/{order['id']}/pay", headers=auth(second_token))
    assert paid.status_code == 200
    assert paid.get_json()["data"]["status"] == "paid"

    done = client.post(f"/api/v1/orders/{order['id']}/complete", headers=auth(second_token))
    assert done.status_code == 200
    assert done.get_json()["data"]["status"] == "completed"

    item = client.get(f"/api/v1/items/{item_id}").get_json()["data"]
    assert item["status"] == "sold"


def test_cancel_restores_item_to_on_sale(client, user_token, second_token, category):
    item_id = _publish(client, user_token, category.id)
    order = _buy(client, second_token, item_id).get_json()["data"]

    resp = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth(second_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "cancelled"

    item = client.get(f"/api/v1/items/{item_id}").get_json()["data"]
    assert item["status"] == "on_sale"


def test_invalid_transition_is_rejected(client, user_token, second_token, category):
    item_id = _publish(client, user_token, category.id)
    order = _buy(client, second_token, item_id).get_json()["data"]

    # 未支付不能确认收货
    resp = client.post(f"/api/v1/orders/{order['id']}/complete", headers=auth(second_token))
    assert resp.status_code == 409

    client.post(f"/api/v1/orders/{order['id']}/pay", headers=auth(second_token))
    # 已支付不能重复支付
    again = client.post(f"/api/v1/orders/{order['id']}/pay", headers=auth(second_token))
    assert again.status_code == 409


def test_seller_can_see_sold_orders(client, user_token, second_token, category):
    item_id = _publish(client, user_token, category.id)
    _buy(client, second_token, item_id)

    resp = client.get("/api/v1/orders", query_string={"role": "seller"}, headers=auth(user_token))
    assert resp.get_json()["data"]["pagination"]["total"] == 1

    buyer_view = client.get("/api/v1/orders", headers=auth(second_token))
    assert buyer_view.get_json()["data"]["pagination"]["total"] == 1


def test_stranger_cannot_read_order(client, user_token, second_token, category):
    item_id = _publish(client, user_token, category.id)
    order = _buy(client, second_token, item_id).get_json()["data"]

    stranger = client.post(
        "/api/v1/auth/register",
        json={"username": "dave", "email": "dave@campus.edu", "password": "Passw0rd!"},
    ).get_json()["data"]["access_token"]
    resp = client.get(f"/api/v1/orders/{order['id']}", headers=auth(stranger))
    assert resp.status_code == 403