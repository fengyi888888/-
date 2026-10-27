"""业务异常与全局错误处理：保证任何路径都返回同一种 JSON 结构。"""

import logging

from flask import Flask
from werkzeug.exceptions import HTTPException

from app import responses

logger = logging.getLogger(__name__)


class AppError(Exception):
    """可预期的业务异常，由全局处理器翻译为统一响应。"""

    def __init__(self, code: int, message: str, status: int = 400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


class ValidationError(AppError):
    def __init__(self, details, message: str = "参数校验失败"):
        super().__init__(responses.CODE_PARAM_INVALID, message, 400, details)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "未登录或凭证无效", code=None):
        super().__init__(code or responses.CODE_UNAUTHORIZED, message, 401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "无权限执行该操作"):
        super().__init__(responses.CODE_FORBIDDEN, message, 403)


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(responses.CODE_NOT_FOUND, message, 404)


class ConflictError(AppError):
    def __init__(self, message: str = "资源状态冲突"):
        super().__init__(responses.CODE_CONFLICT, message, 409)


def register_error_handlers(app: Flask) -> None:
    app.register_error_handler(AppError, _handle_app_error)

    @app.errorhandler(HTTPException)
    def _handle_http_error(exc: HTTPException):
        code = {
            404: responses.CODE_NOT_FOUND,
            405: responses.CODE_PARAM_INVALID,
            401: responses.CODE_UNAUTHORIZED,
        }.get(exc.code, responses.CODE_INTERNAL_ERROR)
        return responses.fail(code, exc.description or exc.name, exc.code or 500)

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):
        logger.exception("unhandled error: %s", exc)
        return responses.fail(
            responses.CODE_INTERNAL_ERROR, "服务器内部错误", 500
        )


def _handle_app_error(exc: AppError):
    if exc.status >= 500:
        logger.error("app error: %s", exc)
    return responses.fail(exc.code, exc.message, exc.status, exc.details)