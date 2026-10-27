"""认证与授权：密码哈希、JWT 签发/校验、登录态装饰器。"""

from datetime import datetime, timezone
from functools import wraps

import jwt
from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from app.errors import ForbiddenError, UnauthorizedError
from app.extensions import db
from app.models import User
from app.responses import CODE_TOKEN_EXPIRED


def hash_password(raw: str) -> str:
    return generate_password_hash(raw, method="pbkdf2:sha256:260000")


def verify_password(raw: str, hashed: str) -> bool:
    return check_password_hash(hashed, raw)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_token(user_id: int, token_type: str = "access", ttl=None) -> str:
    if ttl is None:
        ttl = (
            current_app.config["ACCESS_TOKEN_TTL"]
            if token_type == "access"
            else current_app.config["REFRESH_TOKEN_TTL"]
        )
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": _now(),
        "exp": _now() + ttl,
    }
    return jwt.encode(
        payload, current_app.config["JWT_SECRET"], algorithm=current_app.config["JWT_ALGORITHM"]
    )


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("登录已过期，请重新登录", CODE_TOKEN_EXPIRED) from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("凭证无效") from exc
    if payload.get("type") != expected_type:
        raise UnauthorizedError("凭证类型不匹配")
    return payload


def _load_user_from_header():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[7:].strip()
    if not token:
        return None
    payload = decode_token(token, "access")
    user = db.session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("账号不存在或已停用")
    return user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = _load_user_from_header()
        if user is None:
            raise UnauthorizedError()
        g.current_user = user
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if g.current_user.role != "admin":
            raise ForbiddenError("需要管理员权限")
        return view(*args, **kwargs)

    return wrapper


def optional_login(view):
    """详情页等场景：带 token 就注入用户，不带也放行。"""

    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            g.current_user = _load_user_from_header()
        except UnauthorizedError:
            g.current_user = None
        return view(*args, **kwargs)

    return wrapper