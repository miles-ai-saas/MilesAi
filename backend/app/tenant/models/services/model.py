"""租户模型配置：选用平台内置模型、自定义模型与 BYOK 凭证绑定。"""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access
from app.tenant.models.repositories.model import ModelConfigRepository
from app.tenant.models.schemas.model import (
    ModelBuiltinCredentialsIn,
    ModelCatalogMetaOut,
    ModelConfigCreate,
    ModelConfigOut,
    ModelConfigUpdate,
    ModelTypeOption,
    ModelVendorOption,
)
from app.tenant.models.services.model_resolve import (
    credential_status,
    load_tenant_credential,
)
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService
from app.models.model import ModelConfig
from app.models.model_tenant_credential import ModelTenantCredential
from app.models.model_catalog import (
    CATALOG_MODEL_TYPES,
    MODEL_TYPE_LABELS,
    ModelCapabilityType,
    ModelPublishStatus,
    ModelVendor,
    VENDOR_LABELS,
)
from app.tenant.models.services.api_key_validation import normalize_api_key, validate_api_key

SUPPORTED_VENDORS = (
    ModelVendor.DEEPSEEK,
    ModelVendor.DOUBAO,
    ModelVendor.QWEN,
)


def _to_out(model: ModelConfig, cred: ModelTenantCredential | None) -> ModelConfigOut:
    cs = credential_status(model, cred)
    return ModelConfigOut(
        id=model.id,
        source=model.source,
        name=model.name,
        vendor=model.vendor,
        provider=model.provider,
        model_name=model.model_name,
        model_code=model.model_code,
        model_type=model.model_type,
        description=model.description,
        context_window=model.context_window,
        badge=model.badge,
        api_base=model.api_base,
        is_active=model.is_active,
        publish_status=model.publish_status if model.is_builtin else None,
        credential_status=cs,
        has_api_key=cs in ("platform", "tenant"),
        extra=model.extra or {},
        created_at=model.created_at,
    )


class ModelService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = ModelConfigRepository(db)

    async def catalog_meta(self) -> ModelCatalogMetaOut:
        return ModelCatalogMetaOut(
            vendors=[ModelVendorOption(value=v.value, label=VENDOR_LABELS[v.value]) for v in SUPPORTED_VENDORS],
            model_types=[ModelTypeOption(value=t.value, label=MODEL_TYPE_LABELS[t.value]) for t in CATALOG_MODEL_TYPES],
        )

    async def _get_or_raise(self, config_id: UUID) -> ModelConfig:
        model = await self.repo.get_by_id(config_id)
        if not model or is_marked_deleted(model):
            raise NotFoundError("模型配置不存在")
        if model.tenant_id is not None:
            assert_tenant_access(self.ctx, model.tenant_id)
        return model

    def _tenant_visible_stmt(self):
        return select(ModelConfig).where(
            or_(
                ModelConfig.tenant_id == self.ctx.tenant_id,
                (ModelConfig.tenant_id.is_(None) & (ModelConfig.publish_status == ModelPublishStatus.PUBLISHED.value)),
            ),
            not_deleted(ModelConfig),
        )

    async def list_configs(
        self,
        *,
        vendor: str | None = None,
        model_type: str | None = None,
        source: str | None = None,
        q: str | None = None,
    ) -> list[ModelConfigOut]:
        stmt = self._tenant_visible_stmt().order_by(
            ModelConfig.sort_order.asc(),
            ModelConfig.created_at.desc(),
        )
        if vendor:
            stmt = stmt.where(ModelConfig.vendor == vendor)
        if model_type:
            stmt = stmt.where(ModelConfig.model_type == model_type)
        if source == "builtin":
            stmt = stmt.where(ModelConfig.tenant_id.is_(None))
        elif source == "custom":
            stmt = stmt.where(ModelConfig.tenant_id == self.ctx.tenant_id)
        rows = (await self.db.execute(stmt)).scalars().all()
        if q:
            q_lower = q.lower()
            rows = [m for m in rows if q_lower in (m.name or "").lower() or q_lower in (m.model_code or "").lower() or q_lower in (m.model_name or "").lower()]
        out: list[ModelConfigOut] = []
        for m in rows:
            cred = None
            if m.is_builtin:
                cred = await load_tenant_credential(self.db, self.ctx.tenant_id, m.id)
            out.append(_to_out(m, cred))
        return out

    async def get_config(self, config_id: UUID) -> ModelConfigOut:
        model = await self._get_or_raise(config_id)
        if model.tenant_id is None and model.publish_status != ModelPublishStatus.PUBLISHED.value:
            raise NotFoundError("模型配置不存在")
        cred = None
        if model.is_builtin:
            cred = await load_tenant_credential(self.db, self.ctx.tenant_id, model.id)
        return _to_out(model, cred)

    async def create_config(self, body: ModelConfigCreate) -> ModelConfigOut:
        vendor = body.vendor or ModelVendor.OTHER.value
        provider = body.provider or vendor
        if body.model_type == ModelCapabilityType.EMBEDDING.value:
            extra = body.extra or {}
            if not extra.get("embedding_dimension"):
                raise BadRequestError("向量化模型须在 extra 中配置 embedding_dimension（整数）")
            from app.integrations.embeddings import known_invoke_modes
            from app.common.constants.model_extra import EXTRA_INVOKE_MODE

            mode = extra.get(EXTRA_INVOKE_MODE)
            if isinstance(mode, str) and mode.strip():
                if mode.strip().lower() not in known_invoke_modes():
                    raise BadRequestError(f"不支持的 invoke_mode: {mode}，可选: {', '.join(sorted(known_invoke_modes()))}")
        if body.model_type == ModelCapabilityType.RERANK.value:
            extra = body.extra or {}
            from app.common.constants.model_extra import EXTRA_INVOKE_MODE
            from app.integrations.rerank import known_invoke_modes as rerank_invoke_modes

            mode = extra.get(EXTRA_INVOKE_MODE)
            if isinstance(mode, str) and mode.strip():
                if mode.strip().lower() not in rerank_invoke_modes():
                    raise BadRequestError(f"不支持的 rerank invoke_mode: {mode}，可选: {', '.join(sorted(rerank_invoke_modes()))}")
        model = await self.repo.create(
            tenant_id=self.ctx.tenant_id,
            name=body.name,
            provider=provider,
            model_name=body.model_name,
            model_code=body.model_code,
            vendor=vendor,
            model_type=body.model_type,
            description=body.description,
            api_base=body.api_base,
            api_key_encrypted=validate_api_key(body.api_key, vendor=vendor) if body.api_key else None,
            publish_status=ModelPublishStatus.PUBLISHED.value,
            extra=body.extra,
        )
        await self.db.refresh(model)
        return _to_out(model, None)

    async def update_config(self, config_id: UUID, body: ModelConfigUpdate) -> ModelConfigOut:
        model = await self._get_or_raise(config_id)
        if model.tenant_id is None:
            raise BadRequestError("系统内置模型不可修改")
        data = body.model_dump(exclude_unset=True)
        api_key = data.pop("api_key", None)
        if api_key is not None:
            normalized = normalize_api_key(api_key)
            model.api_key_encrypted = validate_api_key(normalized, vendor=model.vendor) if normalized else None
        if "vendor" in data and data.get("provider") is None:
            data["provider"] = data["vendor"]
        await self.repo.update_fields(model, data)
        await self.db.refresh(model)
        return _to_out(model, None)

    async def delete_config(self, config_id: UUID) -> None:
        model = await self._get_or_raise(config_id)
        if model.tenant_id is None:
            raise BadRequestError("系统内置模型不可删除")
        await mark_deleted(self.db, model)

    async def upsert_builtin_credentials(self, config_id: UUID, body: ModelBuiltinCredentialsIn) -> ModelConfigOut:
        model = await self._get_or_raise(config_id)
        if not model.is_builtin:
            raise BadRequestError("仅内置模型可配置租户密钥")
        cred = await load_tenant_credential(self.db, self.ctx.tenant_id, model.id)
        validated_key = validate_api_key(body.api_key, vendor=model.vendor)
        if cred:
            cred.api_key_encrypted = validated_key
            if body.api_base is not None:
                cred.api_base = body.api_base
            cred.is_active = True
        else:
            self.db.add(
                ModelTenantCredential(
                    tenant_id=self.ctx.tenant_id,
                    model_config_id=model.id,
                    api_key_encrypted=validated_key,
                    api_base=body.api_base,
                    is_active=True,
                )
            )
        await self.db.flush()
        cred = await load_tenant_credential(self.db, self.ctx.tenant_id, model.id)
        return _to_out(model, cred)

    async def delete_builtin_credentials(self, config_id: UUID) -> ModelConfigOut:
        model = await self._get_or_raise(config_id)
        if not model.is_builtin:
            raise BadRequestError("仅内置模型可删除租户密钥")
        cred = await load_tenant_credential(self.db, self.ctx.tenant_id, model.id)
        if cred:
            await self.db.delete(cred)
            await self.db.flush()
        return _to_out(model, None)
