"""HTTP 冒烟测试：对着真实运行的服务跑一遍核心链路。

用法：
    set BASE_URL=http://127.0.0.1:5000
    python scripts/smoke_test.py

覆盖：健康检查 → 注册/登录 → 发布商品（含中文）→ 检索 → 收藏 →
下单/支付/收货 → 并发下单只允许一个买家成功。
"""

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/")
STAMP = str(int(time.time() * 1000))[-6:]
FAILED = []


def call(method: str, path: str, body=None, token=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def check(label: str, condition: bool, detail: str = ""):
    print(f"[{'ok' if condition else 'FAIL'}] {label} {detail}")
    if not condition:
        FAILED.append(label)


def register(username: str):
    status, body = call(
        "POST",
        "/api/v1/auth/register",
        {"username": username, "email": f"{username}@campus.edu", "password": "Passw0rd!"},
    )
    assert status == 201, body
    return body["data"]["access_token"]


def main() -> int:
    status, body = call("GET", "/healthz")
    check("healthz 可用且数据库在线", status == 200 and body["data"]["database"] == "up", str(body["data"]))

    seller = register(f"seller{STAMP}")
    buyer = register(f"buyer{STAMP}")

    status, body = call("POST", "/api/v1/auth/login", {"account": f"buyer{STAMP}", "password": "Passw0rd!"})
    check("登录成功", status == 200, body["message"])

    # 分类存在性由 seed 保证，这里直接取第一个
    status, body = call("GET", "/api/v1/categories")
    category_id = body["data"][0]["id"]
    check("分类列表非空", status == 200 and len(body["data"]) > 0)

    title = f"蓝牙耳机（九成新）{STAMP}"
    status, body = call(
        "POST",
        "/api/v1/items",
        {"title": title, "description": "自用一年，功能完好", "price": "129.90", "category_id": category_id},
        token=seller,
    )
    item_id = body["data"]["id"]
    check("发布商品（中文正常）", status == 201 and body["data"]["title"] == title)
    check("价格按分存储", body["data"]["price_cents"] == 12990, str(body["data"]["price_cents"]))

    status, body = call("GET", f"/api/v1/items?keyword={urllib.parse.quote(title[:4])}")
    check("关键词检索命中", status == 200 and body["data"]["pagination"]["total"] >= 1)

    status, body = call("POST", "/api/v1/favorites", {"item_id": item_id}, token=buyer)
    check("收藏成功", status == 201, body["message"])

    # 并发下单：两个买家同时抢同一件商品
    rival = register(f"rival{STAMP}")
    results: dict[int, int] = {}

    def buy(index: int, token: str):
        results[index] = call("POST", "/api/v1/orders", {"item_id": item_id}, token=token)[0]

    threads = [
        threading.Thread(target=buy, args=(index, token))
        for index, token in enumerate((buyer, rival))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    check("并发下单只有一方成功", sorted(results.values()) == [201, 409], str(sorted(results.values())))

    winner = buyer if results[0] == 201 else rival
    status, body = call("GET", "/api/v1/orders?role=buyer", token=winner)
    order = body["data"]["list"][0]
    check("订单初始状态 pending", order["status"] == "pending", order["status"])

    status, body = call("POST", f"/api/v1/orders/{order['id']}/pay", token=winner)
    check("支付后状态 paid", status == 200 and body["data"]["status"] == "paid")

    status, body = call("POST", f"/api/v1/orders/{order['id']}/complete", token=winner)
    check("确认收货后 completed", status == 200 and body["data"]["status"] == "completed")

    status, body = call("GET", f"/api/v1/items/{item_id}")
    check("商品变为 sold", body["data"]["status"] == "sold", body["data"]["status"])

    status, body = call("POST", f"/api/v1/orders/{order['id']}/cancel", token=winner)
    check("已完成订单不能取消", status == 409, body["message"])

    print()
    if FAILED:
        print(f"失败 {len(FAILED)} 项：{FAILED}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())