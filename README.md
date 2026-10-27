# 校园服务 API（Flask + MySQL）

面向校园二手交易场景的后端服务：用户认证、商品发布与检索、收藏、下单交易全流程。
项目重点在与业务无关的**工程规范**：统一响应体、统一错误码、JWT 双令牌、订单状态机、
接口限流、分页与参数校验，以及可部署、可测试的工程结构。

## 技术栈

| 层次 | 选型 |
| --- | --- |
| Web 框架 | Flask 3.1（应用工厂 + 蓝图） |
| ORM | SQLAlchemy 2.x / Flask-SQLAlchemy 3.1 |
| 数据库 | MySQL 8.0（utf8mb4），测试用 SQLite 内存库 |
| 认证 | PyJWT（HS256，access/refresh 双令牌）+ PBKDF2 密码哈希 |
| 测试 | pytest，34 个用例覆盖认证、商品、订单、权限、限流 |
| 部署 | gunicorn + systemd + nginx（Linux） |

## 目录结构

```
campus-service-api/
├─ app/
│  ├─ __init__.py       应用工厂：配置、扩展、蓝图、错误处理、请求日志
│  ├─ config.py         开发 / 测试 / 生产三套配置，环境变量驱动
│  ├─ extensions.py     db 实例（避免循环导入）
│  ├─ models.py         User / Category / Item / Favorite / Order
│  ├─ security.py       密码哈希、JWT 签发校验、登录态装饰器
│  ├─ errors.py         业务异常 + 全局错误处理器
│  ├─ responses.py      统一响应体、分页封装
│  ├─ validators.py     链式参数校验，字段级错误收集
│  ├─ ratelimit.py      滑动窗口限流（内存实现）
│  ├─ cli.py            init-db / seed / create-admin
│  └─ api/              auth / items / categories / favorites / orders / meta
├─ tests/               pytest 用例（内存库，用例间隔离）
├─ docs/api.md          接口文档
├─ deploy/              gunicorn 配置、systemd unit、nginx 配置
├─ wsgi.py              WSGI 入口
└─ requirements.txt
```

## 快速开始

### 1. 准备环境

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 配置数据库

```bash
cp .env.example .env
```

在 MySQL 中建库建账号：

```sql
CREATE DATABASE campus_service DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'campus'@'localhost' IDENTIFIED BY 'campus_pwd';
GRANT ALL PRIVILEGES ON campus_service.* TO 'campus'@'localhost';
FLUSH PRIVILEGES;
```

`.env` 中的 `DATABASE_URL`：

```
DATABASE_URL=mysql+pymysql://campus:campus_pwd@127.0.0.1:3306/campus_service?charset=utf8mb4
```

### 3. 建表并写入演示数据

```bash
# Windows 用 set，Linux 用 export
set FLASK_APP=wsgi:app
flask init-db
flask seed
```

### 4. 启动

```bash
python wsgi.py            # 开发：http://127.0.0.1:5000
gunicorn -c deploy/gunicorn.conf.py wsgi:app   # 生产（Linux）
```

冒烟验证：

```bash
curl http://127.0.0.1:5000/healthz
```

## 测试

```bash
pytest            # 34 passed
pytest -k orders  # 只跑订单相关
```

测试使用 SQLite 内存库，每个用例独立建表/销毁；`tests/conftest.py` 提供
注册、登录、造商品的公共夹具。

## 接口

完整接口说明见 [docs/api.md](docs/api.md)。核心资源：`auth` / `items` / `categories` /
`favorites` / `orders`，统一挂在 `/api/v1` 下。

## 设计要点

- **统一响应与错误码**：所有出口都是 `{code, message, data}`；参数校验失败在
  `details` 中给出字段级原因，前端可直接定位表单字段。
- **双令牌认证**：access token 30 分钟、refresh token 7 天；令牌类型写入 `type` 声明，
  防止用 access token 去刷新。密码使用 PBKDF2-SHA256，不落明文。
- **订单状态机**：`pending → paid → completed`，`pending/paid → cancelled`；
  非法流转抛 409，业务规则集中在模型方法里，路由层只做权限判断。
- **并发下单**：创建订单时对商品行加 `SELECT ... FOR UPDATE`，并校验商品状态，
  避免同一件商品被两个买家同时锁定（MySQL 下生效）。
- **金额用整数分存储**：用 `Decimal` 解析入参、校验最多两位小数，落库为 `price_cents`，
  彻底避开浮点误差。
- **限流**：登录接口按客户端 IP 做滑动窗口限流（`collections.deque` 存时间戳），
  超限返回 429 与 `retry_after`；多实例部署时可替换为 Redis + ZSET。
- **可观测性**：每个请求生成 `X-Request-Id`，访问日志包含方法、路径、状态码、耗时，
  `/healthz` 真实探活数据库。
- **配置分离**：开发/测试/生产三套配置类，全部由环境变量驱动，代码中不出现密钥。

## 部署（Linux）

```bash
# 服务器上
git clone <repo> /srv/campus-service-api
cd /srv/campus-service-api
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # 填写生产密钥与数据库连接

sudo cp deploy/campus-api.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now campus-api

sudo cp deploy/nginx.conf /etc/nginx/conf.d/campus-api.conf
sudo nginx -t && sudo systemctl reload nginx

curl http://127.0.0.1:8000/healthz
journalctl -u campus-api -f     # 查看日志
```