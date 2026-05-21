from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access
from app.app_tenant.models.repositories.model import ModelConfigRepository
from app.app_tenant.models.schemas.model import ModelConfigCreate, ModelConfigOut, ModelConfigUpdate
from app.core.service import BaseService
from app.models.model import ModelConfig


class ModelService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = ModelConfigRepository(db)

    async def _get_or_raise(self, config_id: UUID) -> ModelConfig:
        model = await self.repo.get_by_id(config_id)
        if not model:
            raise NotFoundError("模型配置不存在")
        if model.tenant_id is not None:
            assert_tenant_access(self.ctx, model.tenant_id)
        return model

    async def list_configs(self) -> list[ModelConfigOut]:
        stmt = select(ModelConfig).where(
            (ModelConfig.tenant_id == self.ctx.tenant_id) | (ModelConfig.tenant_id.is_(None))
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [ModelConfigOut.model_validate(m) for m in rows]

    async def create_config(self, body: ModelConfigCreate) -> ModelConfigOut:
        model = await self.repo.create(
            tenant_id=self.ctx.tenant_id,
            name=body.name,
            provider=body.provider,
            model_name=body.model_name,
            api_base=body.api_base,
            api_key_encrypted=body.api_key,
            extra=body.extra,
        )
        await self.db.refresh(model)
        return ModelConfigOut.model_validate(model)

    async def update_config(self, config_id: UUID, body: ModelConfigUpdate) -> ModelConfigOut:
        model = await self._get_or_raise(config_id)
        if model.tenant_id is None:
            raise BadRequestError("系统内置模型不可修改")
        data = body.model_dump(exclude_unset=True)
        api_key = data.pop("api_key", None)
        if api_key is not None:
            model.api_key_encrypted = api_key
        await self.repo.update_fields(model, data)
        await self.db.refresh(model)
        return ModelConfigOut.model_validate(model)

    async def delete_config(self, config_id: UUID) -> None:
        model = await self._get_or_raise(config_id)
        if model.tenant_id is None:
            raise BadRequestError("系统内置模型不可删除")
        await self.db.delete(model)
