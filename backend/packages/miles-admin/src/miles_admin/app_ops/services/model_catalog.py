"""运营端内置模型目录：发布/下架、平台 Key、与租户 ModelConfig 隔离。"""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_admin.app_ops.schemas.model_catalog import (
    ModelCatalogCreate,
    ModelCatalogImportBody,
    ModelCatalogImportResult,
    ModelCatalogOut,
    ModelCatalogRefsOut,
    ModelCatalogUpdate,
)
from miles_common.api_key import validate_api_key
from miles_common.exceptions import BadRequestError, ConflictError, NotFoundError
from miles_common.schema import PageParams, PageResult
from miles_core.models.agent import Agent
from miles_core.models.kb import KnowledgeBase
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelPublishStatus
from miles_core.soft_delete import is_marked_deleted, mark_deleted, not_deleted

_ICON_EXTRA_KEY = "icon"
_ALLOWED_PUBLISH = frozenset(
    {
        ModelPublishStatus.DRAFT.value,
        ModelPublishStatus.PUBLISHED.value,
        ModelPublishStatus.DEPRECATED.value,
    }
)


def _icon_from_extra(extra: dict | None) -> str | None:
    raw = (extra or {}).get(_ICON_EXTRA_KEY)
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def _set_icon_extra(extra: dict, icon: str | None) -> dict:
    out = dict(extra or {})
    if icon is None:
        return out
    cleaned = str(icon).strip()
    if cleaned:
        out[_ICON_EXTRA_KEY] = cleaned
    else:
        out.pop(_ICON_EXTRA_KEY, None)
    return out


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
        icon=_icon_from_extra(m.extra if isinstance(m.extra, dict) else {}),
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
        """按 ID 取内置模型目录项，不存在抛 ``NotFoundError``。"""
        m = await self._get_builtin(model_id)
        return _admin_out(m)

    async def list_catalog(
        self,
        params: PageParams,
        *,
        vendor: str | None = None,
        publish_status: str | None = None,
    ) -> PageResult[ModelCatalogOut]:
        """分页查询内置模型，可按厂商/发布状态筛选。"""
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

    async def reference_counts(self, model_id: UUID) -> ModelCatalogRefsOut:
        """统计仍绑定该内置模型的智能体与知识库数量。"""
        await self._get_builtin(model_id)
        agents = int(
            await self.db.scalar(
                select(func.count())
                .select_from(Agent)
                .where(Agent.model_config_id == model_id, not_deleted(Agent))
            )
            or 0
        )
        kbs = int(
            await self.db.scalar(
                select(func.count())
                .select_from(KnowledgeBase)
                .where(
                    not_deleted(KnowledgeBase),
                    or_(
                        KnowledgeBase.embedding_model_config_id == model_id,
                        KnowledgeBase.visual_embedding_model_config_id == model_id,
                        KnowledgeBase.rerank_model_config_id == model_id,
                    ),
                )
            )
            or 0
        )
        return ModelCatalogRefsOut(agents=agents, knowledge_bases=kbs, total=agents + kbs)

    async def create(self, body: ModelCatalogCreate) -> ModelCatalogOut:
        """创建内置模型（草稿态）；model_code 重复时抛 ``BadRequestError``。"""
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
        extra = _set_icon_extra({}, body.icon)
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
            extra=extra,
        )
        self.db.add(m)
        await self.db.flush()
        await self.db.refresh(m)
        return _admin_out(m)

    async def update(self, model_id: UUID, body: ModelCatalogUpdate) -> ModelCatalogOut:
        """按需更新内置模型字段；支持传入或显式清除 API Key。"""
        m = await self._get_builtin(model_id)
        data = body.model_dump(exclude_unset=True)
        clear_key = data.pop("clear_api_key", None)
        api_key = data.pop("api_key", None)
        icon = data.pop("icon", None) if "icon" in data else None
        if clear_key:
            m.api_key_encrypted = None
        elif api_key:
            m.api_key_encrypted = validate_api_key(api_key, vendor=m.vendor)
        for k, v in data.items():
            setattr(m, k, v)
        if "vendor" in data and "provider" not in data:
            m.provider = data["vendor"]
        if "icon" in body.model_fields_set:
            m.extra = _set_icon_extra(m.extra if isinstance(m.extra, dict) else {}, icon if icon is not None else "")
        await self.db.flush()
        await self.db.refresh(m)
        return _admin_out(m)

    async def publish(self, model_id: UUID) -> ModelCatalogOut:
        """发布内置模型。"""
        m = await self._get_builtin(model_id)
        m.publish_status = ModelPublishStatus.PUBLISHED.value
        await self.db.flush()
        return _admin_out(m)

    async def deprecate(self, model_id: UUID, *, force: bool = False) -> ModelCatalogOut:
        """下架内置模型并置为停用。

        仍有智能体/知识库引用时默认拒绝；``force=true`` 可强制下架（引用方需自行改绑）。
        """
        m = await self._get_builtin(model_id)
        refs = await self.reference_counts(model_id)
        if refs.total > 0 and not force:
            raise ConflictError(
                f"仍有 {refs.agents} 个智能体、{refs.knowledge_bases} 个知识库引用该模型；"
                "确认下架请传 force=true"
            )
        m.publish_status = ModelPublishStatus.DEPRECATED.value
        m.is_active = False
        await self.db.flush()
        return _admin_out(m)

    async def import_catalog(self, body: ModelCatalogImportBody) -> ModelCatalogImportResult:
        """批量导入内置模型；按 ``model_code`` upsert（不覆盖已有 API Key）。"""
        created = updated = skipped = 0
        errors: list[str] = []
        for item in body.items:
            code = (item.model_code or "").strip()
            if not code:
                errors.append("缺少 model_code")
                skipped += 1
                continue
            status = (item.publish_status or ModelPublishStatus.DRAFT.value).strip().lower()
            if status not in _ALLOWED_PUBLISH:
                errors.append(f"{code}: publish_status 非法")
                skipped += 1
                continue
            existing = (
                await self.db.execute(
                    select(ModelConfig).where(
                        ModelConfig.tenant_id.is_(None),
                        ModelConfig.model_code == code,
                        not_deleted(ModelConfig),
                    )
                )
            ).scalar_one_or_none()
            vendor = item.vendor
            if existing is None:
                m = ModelConfig(
                    tenant_id=None,
                    name=item.name.strip(),
                    vendor=vendor,
                    provider=item.provider or vendor,
                    model_name=item.model_name.strip(),
                    model_code=code,
                    model_type=item.model_type,
                    description=item.description,
                    context_window=item.context_window,
                    api_base=item.api_base,
                    publish_status=status,
                    badge=item.badge,
                    sort_order=item.sort_order,
                    is_featured=item.is_featured,
                    is_active=status != ModelPublishStatus.DEPRECATED.value,
                    extra=_set_icon_extra({}, item.icon),
                )
                self.db.add(m)
                created += 1
                continue
            if not body.upsert:
                errors.append(f"{code}: 已存在且未开启 upsert")
                skipped += 1
                continue
            existing.name = item.name.strip()
            existing.vendor = vendor
            existing.provider = item.provider or vendor
            existing.model_name = item.model_name.strip()
            existing.model_type = item.model_type
            existing.description = item.description
            existing.context_window = item.context_window
            existing.api_base = item.api_base
            existing.badge = item.badge
            existing.sort_order = item.sort_order
            existing.is_featured = item.is_featured
            existing.publish_status = status
            existing.is_active = status != ModelPublishStatus.DEPRECATED.value
            if item.icon is not None:
                existing.extra = _set_icon_extra(
                    existing.extra if isinstance(existing.extra, dict) else {},
                    item.icon,
                )
            updated += 1
        await self.db.flush()
        return ModelCatalogImportResult(
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
        )

    async def delete(self, model_id: UUID) -> None:
        """软删内置模型；已发布模型需先下架。"""
        m = await self._get_builtin(model_id)
        if m.publish_status == ModelPublishStatus.PUBLISHED.value:
            raise BadRequestError("已发布模型请先下架再删除")
        if is_marked_deleted(m):
            return
        await mark_deleted(self.db, m)
