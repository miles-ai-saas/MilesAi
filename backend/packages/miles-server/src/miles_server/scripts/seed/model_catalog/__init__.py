"""内置大模型目录（深度求索 / 豆包 / 通义千问）。

数据按厂商拆在 ``embedding`` / ``deepseek`` / ``doubao`` / ``qwen``；
本模块组装 ``BUILTIN_CATALOG`` 并提供幂等种子写入。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import DEFAULT_API_BASES, ModelPublishStatus
from miles_server.scripts.seed.model_catalog.deepseek import ENTRIES as _DEEPSEEK
from miles_server.scripts.seed.model_catalog.doubao import ENTRIES as _DOUBAO
from miles_server.scripts.seed.model_catalog.embedding import ENTRIES as _EMBEDDING
from miles_server.scripts.seed.model_catalog.qwen import ENTRIES as _QWEN

# model_code 与 API model_name 一致，便于租户直接填写调用
BUILTIN_CATALOG: list[dict] = [
    *_EMBEDDING,
    *_DEEPSEEK,
    *_DOUBAO,
    *_QWEN,
]

_RETIRED_BUILTIN_MODEL_CODES = frozenset({"deepseek-reasoner", "deepseek-chat"})
_RETIRED_MODEL_DESCRIPTION = "已退役；请迁移至 deepseek-v4-flash（对话/思考）或 deepseek-v4-pro（复杂推理）。"

_UPDATABLE = (
    "name",
    "provider",
    "model_name",
    "model_type",
    "description",
    "context_window",
    "publish_status",
    "is_featured",
    "badge",
    "sort_order",
    "api_base",
    "is_active",
)


async def _deprecate_retired_catalog_models(session: AsyncSession) -> int:
    """将已移出种子的内置模型标记为 deprecated（保留行以免租户引用断裂）。"""
    rows = (
        (
            await session.execute(
                select(ModelConfig).where(
                    ModelConfig.tenant_id.is_(None),
                    ModelConfig.model_code.in_(_RETIRED_BUILTIN_MODEL_CODES),
                )
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        row.publish_status = ModelPublishStatus.DEPRECATED.value
        row.is_active = False
        row.is_featured = False
        row.description = _RETIRED_MODEL_DESCRIPTION
    return len(rows)


async def seed_model_catalog(session: AsyncSession) -> None:
    """插入或更新内置目录（按 model_code 幂等）。"""
    for item in BUILTIN_CATALOG:
        code = item["model_code"]
        existing = (
            await session.execute(
                select(ModelConfig).where(
                    ModelConfig.tenant_id.is_(None),
                    ModelConfig.model_code == code,
                )
            )
        ).scalar_one_or_none()
        vendor = item["vendor"]
        values = {
            "name": item["name"],
            "vendor": vendor,
            "provider": item["provider"],
            "model_name": item["model_name"],
            "model_type": item["model_type"],
            "description": item.get("description"),
            "context_window": item.get("context_window"),
            "publish_status": ModelPublishStatus.PUBLISHED.value,
            "is_featured": item.get("is_featured", False),
            "badge": item.get("badge"),
            "sort_order": item.get("sort_order", 0),
            "api_base": item.get("api_base") or DEFAULT_API_BASES.get(vendor),
            "is_active": True,
        }
        if existing:
            for key in _UPDATABLE:
                setattr(existing, key, values[key])
            if item.get("extra"):
                existing.extra = item["extra"]
            continue
        session.add(
            ModelConfig(
                tenant_id=None,
                model_code=code,
                capabilities=[],
                extra=item.get("extra") or {},
                **values,
            )
        )
    retired = await _deprecate_retired_catalog_models(session)
    if retired:
        print(f">>> model catalog: deprecated {retired} retired builtin model(s)")


__all__ = ["BUILTIN_CATALOG", "seed_model_catalog"]
