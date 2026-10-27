"""轻量参数校验：不引入额外依赖，把错误字段一次性收集后抛出。"""

import re

from app.errors import ValidationError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class Validator:
    """以链式调用收集错误，最后 `check()` 统一抛出。"""

    def __init__(self, payload):
        self.payload = payload if isinstance(payload, dict) else {}
        self.errors: dict[str, str] = {}

    def _raw(self, field: str):
        return self.payload.get(field)

    def required_str(self, field: str, *, min_len=1, max_len=None) -> "Validator":
        value = self._raw(field)
        if not isinstance(value, str) or not value.strip():
            self.errors[field] = "不能为空"
            return self
        value = value.strip()
        if len(value) < min_len:
            self.errors[field] = f"长度不能少于 {min_len} 个字符"
        elif max_len and len(value) > max_len:
            self.errors[field] = f"长度不能超过 {max_len} 个字符"
        return self

    def pattern(self, field: str, regex: re.Pattern, message: str) -> "Validator":
        value = self._raw(field)
        if isinstance(value, str) and value and not regex.match(value):
            self.errors[field] = message
        return self

    def positive_int(self, field: str, *, maximum=None) -> "Validator":
        value = self._raw(field)
        if isinstance(value, bool) or not isinstance(value, int):
            self.errors[field] = "必须是整数"
        elif value <= 0:
            self.errors[field] = "必须大于 0"
        elif maximum is not None and value > maximum:
            self.errors[field] = f"不能超过 {maximum}"
        return self

    def optional_int(self, field: str) -> "Validator":
        value = self._raw(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            self.errors[field] = "必须是整数"
        return self

    def in_choices(self, field: str, choices, *, required=True) -> "Validator":
        value = self._raw(field)
        if value is None and not required:
            return self
        if value not in choices:
            self.errors[field] = f"必须是 {sorted(choices)} 之一"
        return self

    def check(self) -> dict:
        if self.errors:
            raise ValidationError(self.errors)
        return self.payload