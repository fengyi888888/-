"""滑动窗口限流：内存实现，单机够用；多实例可换成 Redis + ZSET。

装饰器按「动作 + 客户端标识」计数，超限直接抛 429。
"""

import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import current_app, request

from app.errors import AppError
from app.responses import CODE_TOO_MANY_REQUESTS

_lock = threading.Lock()
_buckets: dict[str, deque] = defaultdict(deque)


def _client_key() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limit(action: str, window: int | None = None, maximum: int | None = None):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            win = window or current_app.config["LOGIN_RATE_LIMIT_WINDOW"]
            cap = maximum or current_app.config["LOGIN_RATE_LIMIT_MAX"]
            key = f"rl:{action}:{_client_key()}"
            now = time.monotonic()
            with _lock:
                bucket = _buckets[key]
                while bucket and bucket[0] <= now - win:
                    bucket.popleft()
                if len(bucket) >= cap:
                    retry_after = max(1, int(bucket[0] + win - now))
                    raise AppError(
                        CODE_TOO_MANY_REQUESTS,
                        "请求过于频繁，请稍后再试",
                        429,
                        {"retry_after": retry_after},
                    )
                bucket.append(now)
            return view(*args, **kwargs)

        return wrapper

    return decorator


def reset_buckets() -> None:
    """测试用：清空计数。"""
    with _lock:
        _buckets.clear()