"""统一响应体：{code, message, data}，code=0 表示成功。"""

from flask import jsonify, request

CODE_OK = 0

CODE_PARAM_INVALID = 40001
CODE_UNAUTHORIZED = 40101
CODE_TOKEN_EXPIRED = 40102
CODE_FORBIDDEN = 40301
CODE_NOT_FOUND = 40401
CODE_CONFLICT = 40901
CODE_TOO_MANY_REQUESTS = 42901
CODE_INTERNAL_ERROR = 50001


def ok(data=None, message: str = "ok", status: int = 200):
    return jsonify({"code": CODE_OK, "message": message, "data": data}), status


def paginated(items, total: int, page: int, size: int, message: str = "ok"):
    payload = {
        "list": items,
        "pagination": {
            "page": page,
            "size": size,
            "total": total,
            "pages": (total + size - 1) // size,
        },
    }
    return ok(payload, message=message)


def fail(code: int, message: str, status: int, details=None):
    body = {"code": code, "message": message, "data": None}
    if details is not None:
        body["details"] = details
    return jsonify(body), status


def current_page_args():
    """解析并收敛分页参数，越界值回落到默认值。"""
    from flask import current_app

    default = current_app.config["PAGE_SIZE_DEFAULT"]
    maximum = current_app.config["PAGE_SIZE_MAX"]
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        size = int(request.args.get("size", default))
    except (TypeError, ValueError):
        size = default
    size = min(max(size, 1), maximum)
    return page, size