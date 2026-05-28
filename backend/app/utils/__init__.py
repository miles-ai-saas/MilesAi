"""通用工具函数（无业务域归属）。

注意：勿在此包 ``__init__`` 中导入 ``health_checks``（会经 storage → ORM 形成循环引用）。
健康检查请 ``from app.utils.health_checks import collect_health_status``。
"""

from app.utils.idgen import generate_id, generate_uuid, is_uuid7, uuid7_version
from app.utils.orm import idx, ref_uuid, rel_foreign_keys, uk, un
from app.utils.redis_keys import RedisKeys

__all__ = [
    "generate_id",
    "generate_uuid",
    "uuid7_version",
    "is_uuid7",
    "RedisKeys",
    "ref_uuid",
    "idx",
    "uk",
    "un",
    "rel_foreign_keys",
]
