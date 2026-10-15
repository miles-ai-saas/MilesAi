"""内置大模型目录（深度求索 / 豆包 / 通义千问）。

数据按厂商拆在 ``embedding`` / ``deepseek`` / ``doubao`` / ``qwen``；
本模块组装 ``BUILTIN_CATALOG`` 并提供幂等种子写入。
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import DEFAULT_API_BASES, ModelPublishStatus
from miles_core.models.model.tenant_credential import ModelTenantCredential
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

# 已移出种子的内置 model_code：seed 时物理删除（含租户 BYOK 覆盖），不留 deprecated 行
_RETIRED_BUILTIN_MODEL_CODES = frozenset(
    {
        # DeepSeek
        "deepseek-reasoner",
        "deepseek-chat",
        "deepseek-v4-flash",
        # 豆包 Seed 1.6 / 经典系列
        "doubao-seed-1-6-251015",
        "doubao-seed-1-6-thinking-251015",
        "doubao-seed-1-6-flash-251015",
        "doubao-seed-1-6-lite-251015",
        "doubao-pro-32k",
        "doubao-lite-32k",
        "doubao-1-5-vision-pro-32k-250115",
        "doubao-seedream-4-0-250828",
        "doubao-seededit-3-0-i2i-250628",
        # 通义旧旗舰 / 万相 2.2
        "qwen3-max",
        "qwen3.5-plus",
        "qwen3.5-flash",
        "qwen-turbo",
        "qwen3-235b-a22b-instruct-2507",
        "qwen3-235b-a22b-thinking-2507",
        "qwen-vl-max",
        "qwen-vl-plus",
        "wan2.2-t2i-flash",
        "wan2.2-s2v",
        "wan2.2-i2v-plus",
    }
)

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


async def _purge_retired_catalog_models(session: AsyncSession) -> int:
    """物理删除已移出种子的内置模型及其租户 BYOK 覆盖。"""
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
    if not rows:
        return 0
    ids = [row.id for row in rows]
    await session.execute(
        delete(ModelTenantCredential).where(ModelTenantCredential.model_config_id.in_(ids))
    )
    for row in rows:
        await session.delete(row)
    return len(rows)


async def seed_model_catalog(session: AsyncSession) -> None:
    """插入或更新内置目录（按 model_code 幂等）；旧型号直接删除。"""
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
    purged = await _purge_retired_catalog_models(session)
    if purged:
        print(f">>> model catalog: purged {purged} retired builtin model(s)")


__all__ = ["BUILTIN_CATALOG", "seed_model_catalog"]
