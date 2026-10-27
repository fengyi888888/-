"""认证接口：注册、登录、刷新令牌、当前用户。"""

from flask import Blueprint, g, request
from sqlalchemy import or_

from app.errors import ConflictError, UnauthorizedError
from app.extensions import db
from app.models import User
from app.ratelimit import rate_limit
from app.responses import ok
from app.security import (
    create_token,
    decode_token,
    hash_password,
    login_required,
    verify_password,
)
from app.validators import EMAIL_RE, USERNAME_RE, Validator

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.post("/register")
def register():
    payload = Validator(request.get_json(silent=True)) \
        .required_str("username", min_len=3, max_len=32) \
        .pattern("username", USERNAME_RE, "只能包含字母、数字、下划线，长度 3-32") \
        .required_str("email", max_len=120) \
        .pattern("email", EMAIL_RE, "邮箱格式不正确") \
        .required_str("password", min_len=8, max_len=64) \
        .check()

    exists = db.session.execute(
        db.select(User).where(
            or_(User.username == payload["username"], User.email == payload["email"])
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("用户名或邮箱已被注册")

    user = User(
        username=payload["username"],
        email=payload["email"],
        password_hash=hash_password(payload["password"]),
    )
    db.session.add(user)
    db.session.commit()
    return ok(
        {
            "user": user.to_dict(),
            "access_token": create_token(user.id, "access"),
            "refresh_token": create_token(user.id, "refresh"),
        },
        message="注册成功",
        status=201,
    )


@bp.post("/login")
@rate_limit("login")
def login():
    payload = Validator(request.get_json(silent=True)) \
        .required_str("account", max_len=120) \
        .required_str("password", max_len=64) \
        .check()

    user = db.session.execute(
        db.select(User).where(
            or_(User.username == payload["account"], User.email == payload["account"])
        )
    ).scalar_one_or_none()
    if user is None or not verify_password(payload["password"], user.password_hash):
        raise UnauthorizedError("账号或密码错误")
    if not user.is_active:
        raise UnauthorizedError("账号已停用")

    return ok(
        {
            "user": user.to_dict(),
            "access_token": create_token(user.id, "access"),
            "refresh_token": create_token(user.id, "refresh"),
        },
        message="登录成功",
    )


@bp.post("/refresh")
def refresh():
    payload = Validator(request.get_json(silent=True)).required_str("refresh_token").check()
    claims = decode_token(payload["refresh_token"], "refresh")
    user = db.session.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("账号不存在或已停用")
    return ok({"access_token": create_token(user.id, "access")}, message="刷新成功")


@bp.get("/me")
@login_required
def me():
    return ok(g.current_user.to_dict())