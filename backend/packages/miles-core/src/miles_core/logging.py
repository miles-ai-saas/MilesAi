"""统一日志配置（stdlib logging）。

用法（各模块一行，不要自行 basicConfig）::

    from miles_core.logging import get_logger

    logger = get_logger(__name__)

    logger.info("...")
    logger.exception("...")  # 带堆栈

在 API / Celery 进程入口调用 ``setup_logging()``（``create_app`` lifespan、``cli serve`` 已接入）。
"""

from __future__ import annotations

import logging
import logging.config

from miles_core.config import get_settings

_configured = False


def setup_logging() -> None:
    """按环境配置 root 与常见第三方 logger（幂等）。"""
    global _configured
    if _configured:
        return

    settings = get_settings()
    level_name = (settings.log_level or "INFO").upper()
    if not hasattr(logging, level_name):
        level_name = "INFO"

    sqlalchemy_level = logging.INFO if settings.debug else logging.WARNING
    access_level = logging.INFO if settings.debug else logging.WARNING
    litellm_level = getattr(logging, settings.litellm_log.upper(), logging.ERROR)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                    "formatter": "standard",
                    "level": level_name,
                },
            },
            "root": {
                "level": level_name,
                "handlers": ["console"],
            },
            "loggers": {
                "uvicorn": {"level": level_name, "propagate": True},
                "uvicorn.error": {"level": level_name, "propagate": True},
                "uvicorn.access": {"level": access_level, "propagate": True},
                "sqlalchemy.engine": {"level": sqlalchemy_level, "propagate": True},
                "sqlalchemy.pool": {"level": sqlalchemy_level, "propagate": True},
                "celery": {"level": level_name, "propagate": True},
                "httpx": {"level": "WARNING", "propagate": True},
                "httpcore": {"level": "WARNING", "propagate": True},
                "LiteLLM": {"level": litellm_level, "propagate": True},
                "litellm": {"level": litellm_level, "propagate": True},
            },
        }
    )

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """返回命名 logger；首次调用时自动 ``setup_logging()``。"""
    setup_logging()
    return logging.getLogger(name)
