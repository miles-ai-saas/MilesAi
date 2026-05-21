"""UUIDv7 时间有序 ID 生成（数据库主键等）。"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

# RFC 9562 UUIDv7: 48 位毫秒时间戳 + 版本 7 + 12 位随机 + variant(10) + 62 位随机
_VARIANT_10 = 0b10 << 62
_VERSION_7 = 7 << 76


def generate_id() -> str:
    """
    生成 UUIDv7 格式的唯一 ID（时间有序）。
    返回 32 位小写十六进制字符串（无连字符）。
    """
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    uuid_int = (timestamp_ms << 80) | _VERSION_7 | (rand_a << 64) | _VARIANT_10 | rand_b
    return uuid_int.to_bytes(16, "big").hex()


def generate_uuid() -> uuid.UUID:
    """供 SQLAlchemy / PostgreSQL UUID 列使用的 UUIDv7 对象。"""
    return uuid.UUID(hex=generate_id())


def uuid7_version(value: uuid.UUID) -> int:
    """读取 UUID 版本号（兼容 Python 3.12 对 v7 的 .version 可能为 None）。"""
    return (value.int >> 76) & 0xF


def is_uuid7(value: uuid.UUID | str) -> bool:
    """判断是否为 UUIDv7。"""
    try:
        parsed = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except ValueError:
        return False
    return uuid7_version(parsed) == 7 and (parsed.int >> 62) & 0x3 == 0b10
