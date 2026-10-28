"""应用配置：开发 / 测试 / 生产三套，全部由环境变量驱动。"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# 显式指定 .env 位置：不依赖启动时的工作目录，避免从别的目录启动就读不到配置
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key-change-in-production")
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-jwt-secret-change-in-production")
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_TTL = timedelta(seconds=_env_int("ACCESS_TOKEN_TTL", 1800))
    REFRESH_TOKEN_TTL = timedelta(seconds=_env_int("REFRESH_TOKEN_TTL", 604800))

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///campus_service.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "pool_size": 5,
        "max_overflow": 10,
    }

    LOGIN_RATE_LIMIT_WINDOW = _env_int("LOGIN_RATE_LIMIT_WINDOW", 60)
    LOGIN_RATE_LIMIT_MAX = _env_int("LOGIN_RATE_LIMIT_MAX", 10)

    PAGE_SIZE_DEFAULT = 10
    PAGE_SIZE_MAX = 50
    JSON_AS_ASCII = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    ACCESS_TOKEN_TTL = timedelta(minutes=30)


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_size": 20,
        "max_overflow": 40,
    }


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None):
    env = name or os.getenv("FLASK_ENV", "development")
    return CONFIGS.get(env, DevelopmentConfig)