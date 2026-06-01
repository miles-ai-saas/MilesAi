"""系统配置项读写与运行时信息（版本、特性开关等）。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.tenant import TenantContext
from app.models.platform.system import SystemConfig
from app.tenant.system.schemas.config import (
    ConfigDefinitionOut,
    RuntimeInfoOut,
    SystemConfigOut,
    SystemConfigUpsert,
)
from app.core.service import BaseService
from app.utils.health_checks import collect_health_status

CONFIG_DEFINITIONS: list[dict] = [
    {
        "key": "rag.default_chunk_size",
        "label": "默认分片大小",
        "category": "知识库",
        "description": "新建知识库时的默认 chunk_size",
        "default_value": 500,
    },
    {
        "key": "rag.default_chunk_overlap",
        "label": "默认分片重叠",
        "category": "知识库",
        "description": "新建知识库时的默认 chunk_overlap",
        "default_value": 50,
    },
    {
        "key": "ingest.max_file_mb",
        "label": "单文件大小上限(MB)",
        "category": "知识库",
        "description": "文档上传大小限制提示（业务层校验可后续接入）",
        "default_value": 50,
    },
]


def _format_component_status(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("status", value))
    if isinstance(value, bool):
        return "ok" if value else "unavailable"
    return str(value)


class SystemConfigService(BaseService):
    """平台键值配置与 /health 运行时信息（合并 CONFIG_DEFINITIONS 默认值）。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def list_definitions(self) -> list[ConfigDefinitionOut]:
        """管理端展示项：定义元数据 + 库中当前值或 default。"""
        stored = {row.key: row for row in (await self.db.execute(select(SystemConfig))).scalars().all()}
        out: list[ConfigDefinitionOut] = []
        for d in CONFIG_DEFINITIONS:
            row = stored.get(d["key"])
            val = row.value if row else d["default_value"]
            if isinstance(val, dict) and "value" in val:
                display = val.get("value")
            else:
                display = val
            out.append(
                ConfigDefinitionOut(
                    key=d["key"],
                    label=d["label"],
                    category=d["category"],
                    description=d["description"],
                    value_type="number" if isinstance(display, (int, float)) else "string",
                    default_value=display,
                )
            )
        return out

    async def list_configs(self) -> list[SystemConfigOut]:
        rows = (await self.db.execute(select(SystemConfig).order_by(SystemConfig.key))).scalars().all()
        return [
            SystemConfigOut(
                key=r.key,
                value=r.value,
                description=r.description,
                is_encrypted=r.is_encrypted,
            )
            for r in rows
        ]

    async def upsert_config(self, key: str, body: SystemConfigUpsert) -> SystemConfigOut:
        row = await self.db.scalar(select(SystemConfig).where(SystemConfig.key == key))
        payload = body.value if isinstance(body.value, dict) else {"value": body.value}
        if row:
            row.value = payload
            if body.description is not None:
                row.description = body.description
        else:
            row = SystemConfig(
                key=key,
                value=payload,
                description=body.description,
            )
            self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return SystemConfigOut(
            key=row.key,
            value=row.value,
            description=row.description,
            is_encrypted=row.is_encrypted,
        )

    async def runtime_info(self) -> RuntimeInfoOut:
        settings = get_settings()
        health = await collect_health_status()
        components = {k: _format_component_status(v) for k, v in health.get("components", {}).items()}
        preview = {
            "database_url": "***" if settings.database_url else None,
            "redis_url": "***" if settings.redis_url else None,
            "object_storage_backend": settings.object_storage_backend,
            "object_storage_endpoint": settings.object_storage_endpoint,
            "object_storage_bucket": settings.object_storage_bucket,
            "vector_store_backend": settings.vector_store_backend,
            "weaviate_url": settings.weaviate_url,
            "celery_broker": "***" if settings.celery_broker_url else None,
            "default_embedding": getattr(settings, "embedding_model", None),
        }
        return RuntimeInfoOut(components=components, settings_preview=preview)
