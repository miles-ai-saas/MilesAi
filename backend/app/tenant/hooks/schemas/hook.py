from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.hooks.models import HookScope, HookTrigger, HookType


class HookDefinitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    hook_type: HookType = HookType.HTTP
    config: dict = Field(default_factory=dict)
    trigger: HookTrigger = HookTrigger.BEFORE_CALL
    scope: HookScope = HookScope.GLOBAL
    target_id: UUID | None = None
    priority: int = 100


class HookDefinitionUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class HookDefinitionOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    hook_type: HookType
    config: dict
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class HookBindingCreate(BaseModel):
    scope: HookScope = HookScope.GLOBAL
    target_id: UUID | None = None
    trigger: HookTrigger = HookTrigger.BEFORE_CALL
    priority: int = 100


class HookBindingOut(BaseModel):
    id: UUID
    hook_id: UUID
    scope: HookScope
    target_id: UUID | None
    trigger: HookTrigger
    priority: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
