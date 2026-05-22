from uuid import UUID

from pydantic import BaseModel, Field


class PermissionOut(BaseModel):
    id: UUID
    code: str
    name: str
    module: str
    description: str | None = None

    model_config = {"from_attributes": True}


class PermissionGroupOut(BaseModel):
    module: str
    permissions: list[PermissionOut]


class RoleOut(BaseModel):
    id: UUID
    tenant_id: UUID | None
    name: str
    code: str
    description: str | None
    is_system: bool
    permission_codes: list[str] = []

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=1, max_length=64)
    description: str | None = None
    permission_ids: list[UUID] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_ids: list[UUID] | None = None
