"""运营端内置模型目录：发布/下架、平台 Key、与租户 ModelConfig 隔离。"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.app_ops.schemas.model_catalog import (
    ModelCatalogCreate,
    ModelCatalogOut,
    ModelCatalogUpdate,
)
from app.common.exceptions import BadRequestError, NotFoundError
from app.common.schema import PageParams, PageResult
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.models.model import ModelConfig
from app.models.model.catalog import ModelPublishStatus
from app.common.api_key import validate_api_key


def _admin_out(m: ModelConfig) -> ModelCatalogOut:
    return ModelCatalogOut(
        id=m.id,
        name=m.name,
        vendor=m.vendor,
        provider=m.provider,
        model_name=m.model_name,
        model_code=m.model_code,
        model_type=m.model_type,
        description=m.description,
        context_window=m.context_window,
        badge=m.badge,
        sort_order=m.sort_order,
        is_featured=m.is_featured,
        publish_status=m.publish_status,
        is_active=m.is_active,
        api_base=m.api_base,
        has_api_key=bool(m.api_key_encrypted),
        created_at=m.created_at,
    )


class AdminModelCatalogService:
    """管理 tenant_id IS NULL 的平台 ModelConfig（对话/向量化等能力类型）。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_builtin(self, model_id: UUID) -> ModelConfig:
        m = (
            await self.db.execute(
                select(ModelConfig).where(
                    ModelConfig.id == model_id,
                    ModelConfig.tenant_id.is_(None),
                    not_deleted(ModelConfig),
                )
            )
        ).scalar_one_or_none()
        if not m:
            raise NotFoundError("内置模型不存在")
        return m

    async def get(self, model_id: UUID) -> ModelCatalogOut:
        m = await self._get_builtin(model_id)
        return _admin_out(m)

    async def list_catalog(
        self,
        params: PageParams,
        *,
        vendor: str | None = None,
        publish_status: str | None = None,
    ) -> PageResult[ModelCatalogOut]:
        stmt = select(ModelConfig).where(
            ModelConfig.tenant_id.is_(None),
            not_deleted(ModelConfig),
        )
        if vendor:
            stmt = stmt.where(ModelConfig.vendor == vendor)
        if publish_status:
            stmt = stmt.where(ModelConfig.publish_status == publish_status)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(await self.db.scalar(count_stmt) or 0)
        stmt = stmt.order_by(ModelConfig.sort_order.asc(), ModelConfig.created_at.desc())
        rows = (await self.db.execute(stmt.offset((params.page - 1) * params.size).limit(params.size))).scalars().all()
        return PageResult(
            items=[_admin_out(m) for m in rows],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def create(self, body: ModelCatalogCreate) -> ModelCatalogOut:
        dup = (
            await self.db.execute(
                select(ModelConfig).where(
                    ModelConfig.tenant_id.is_(None),
                    ModelConfig.model_code == body.model_code,
                    not_deleted(ModelConfig),
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise BadRequestError(f"model_code 已存在: {body.model_code}")
        vendor = body.vendor
        m = ModelConfig(
            tenant_id=None,
            name=body.name,
            vendor=vendor,
            provider=body.provider or vendor,
            model_name=body.model_name,
            model_code=body.model_code,
            model_type=body.model_type,
            description=body.description,
            context_window=body.context_window,
            api_base=body.api_base,
            api_key_encrypted=validate_api_key(body.api_key, vendor=vendor) if body.api_key else None,
            publish_status=ModelPublishStatus.DRAFT.value,
            badge=body.badge,
            sort_order=body.sort_order,
            is_featured=body.is_featured,
            is_active=True,
            extra={},
        )
        self.db.add(m)
        await self.db.flush()
        await self.db.refresh(m)
        return _admin_out(m)

    async def update(self, model_id: UUID, body: ModelCatalogUpdate) -> ModelCatalogOut:
        m = await self._get_builtin(model_id)
        data = body.model_dump(exclude_unset=True)
        clear_key = data.pop("clear_api_key", None)
        api_key = data.pop("api_key", None)
        if clear_key:
            m.api_key_encrypted = None
        elif api_key:
            m.api_key_encrypted = validate_api_key(api_key, vendor=m.vendor)
        for k, v in data.items():
            setattr(m, k, v)
        if "vendor" in data and "provider" not in data:
            m.provider = data["vendor"]
        await self.db.flush()
        await self.db.refresh(m)
        return _admin_out(m)

    async def publish(self, model_id: UUID) -> ModelCatalogOut:
        m = await self._get_builtin(model_id)
        m.publish_status = ModelPublishStatus.PUBLISHED.value
        await self.db.flush()
        return _admin_out(m)

    async def deprecate(self, model_id: UUID) -> ModelCatalogOut:
        m = await self._get_builtin(model_id)
        m.publish_status = ModelPublishStatus.DEPRECATED.value
        m.is_active = False
        await self.db.flush()
        return _admin_out(m)

    async def delete(self, model_id: UUID) -> None:
        m = await self._get_builtin(model_id)
        if m.publish_status == ModelPublishStatus.PUBLISHED.value:
            raise BadRequestError("已发布模型请先下架再删除")
        if is_marked_deleted(m):
            return
        await mark_deleted(self.db, m)
