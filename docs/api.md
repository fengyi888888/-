# 校园服务 API · 接口文档

Base URL：`http://127.0.0.1:8000/api/v1`

## 统一响应

```json
{ "code": 0, "message": "ok", "data": { } }
```

| code | 含义 | HTTP |
| --- | --- | --- |
| 0 | 成功 | 200 / 201 |
| 40001 | 参数校验失败（`details` 给出字段级原因） | 400 |
| 40101 | 未登录 / 凭证无效 | 401 |
| 40102 | 令牌过期 | 401 |
| 40301 | 无权限 | 403 |
| 40401 | 资源不存在 | 404 |
| 40901 | 状态冲突（重复注册、商品已被下单等） | 409 |
| 42901 | 触发限流（`details.retry_after` 为秒数） | 429 |
| 50001 | 服务端异常 | 500 |

## 认证

需要登录的接口统一携带请求头：

```
Authorization: Bearer <access_token>
```

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/auth/register` | 注册，返回用户信息与双令牌 | 公开 |
| POST | `/auth/login` | 登录（按 IP 限流） | 公开 |
| POST | `/auth/refresh` | 用 refresh_token 换新 access_token | 公开 |
| GET | `/auth/me` | 当前用户 | 登录 |

```http
POST /api/v1/auth/register
Content-Type: application/json

{ "username": "alice", "email": "alice@campus.edu", "password": "Passw0rd!" }
```

```json
{
  "code": 0,
  "message": "注册成功",
  "data": {
    "user": { "id": 1, "username": "alice", "email": "alice@campus.edu", "role": "user" },
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi..."
  }
}
```

## 商品

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/items` | 列表：`keyword` `category_id` `min_price` `max_price` `sort` `page` `size` | 公开 |
| GET | `/items/{id}` | 详情（浏览量 +1） | 公开 |
| GET | `/items/mine` | 我发布的 | 登录 |
| POST | `/items` | 发布 | 登录 |
| PATCH | `/items/{id}` | 修改（仅发布者） | 登录 |
| DELETE | `/items/{id}` | 下架（仅发布者） | 登录 |

`sort` 取值：`latest`（默认）、`price_asc`、`price_desc`、`popular`。

分页响应结构：

```json
{
  "code": 0,
  "data": {
    "list": [ { "id": 1, "title": "数据结构教材", "price": 28.0, "price_cents": 2800 } ],
    "pagination": { "page": 1, "size": 10, "total": 1, "pages": 1 }
  }
}
```

## 分类

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/categories` | 分类列表 | 公开 |
| POST | `/categories` | 新增 | 管理员 |
| PATCH | `/categories/{id}` | 修改 | 管理员 |
| DELETE | `/categories/{id}` | 删除（分类下有商品时拒绝） | 管理员 |

## 收藏

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/favorites` | 我的收藏（分页，含商品信息） | 登录 |
| POST | `/favorites` | 收藏，body `{"item_id": 3}` | 登录 |
| DELETE | `/favorites/{item_id}` | 取消收藏 | 登录 |

## 订单

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | `/orders` | 下单，body `{"item_id": 3}` | 登录（不能买自己的） |
| GET | `/orders` | 我的订单，`role=buyer\|seller`、`status` 过滤 | 登录 |
| GET | `/orders/{id}` | 订单详情 | 买卖双方 |
| POST | `/orders/{id}/pay` | 支付 | 买家 |
| POST | `/orders/{id}/complete` | 确认收货（商品置为已售） | 买家 |
| POST | `/orders/{id}/cancel` | 取消（商品回到在售） | 买卖双方 |

订单状态机：

```
pending --pay--> paid --complete--> completed
   |                |
   +---- cancel ----+--> cancelled   （商品恢复 on_sale）
```

商品状态：`on_sale`（在售）→ `locked`（交易中）→ `sold`（已售）/ `off_shelf`（已下架）。

## 运维

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/healthz` | 探活，数据库不可用时返回 503 |
| GET | `/api/v1/meta` | 服务元信息 |

## 限流

登录接口按客户端 IP 做滑动窗口限流，默认 60 秒 10 次；超限返回 429 并给出 `retry_after`。