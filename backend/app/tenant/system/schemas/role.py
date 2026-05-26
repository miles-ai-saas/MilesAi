from uuid import UUID

from pydantic import BaseModel, Field


class PermissionOut(BaseModel):
    id: UUID = Field(description="权限 ID")
    code: str = Field(description="权限编码")
    name: str = Field(description="权限名称")
    module: str = Field(description="所属模块")
    description: str | None = Field(default=None, description="权限说明")

    model_config = {"from_attributes": True}


class PermissionGroupOut(BaseModel):
    module: str = Field(description="模块名称")
    permissions: list[PermissionOut] = Field(description="该模块下的权限列表")


class RoleOut(BaseModel):
    id: UUID = Field(description="角色 ID")
    tenant_id: UUID | None = Field(default=None, description="租户 ID（系统角色为空）")
    name: str = Field(description="角色名称")
    code: str = Field(description="角色编码")
    description: str | None = Field(default=None, description="角色说明")
    is_system: bool = Field(description="是否为系统内置角色")
    permission_codes: list[str] = Field(default_factory=list, description="权限编码列表")

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="角色名称")
    code: str = Field(..., min_length=1, max_length=64, description="角色编码")
    description: str | None = Field(default=None, description="角色说明")
    permission_ids: list[UUID] = Field(default_factory=list, description="权限 ID 列表")


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, description="角色名称")
    description: str | None = Field(default=None, description="角色说明")
    permission_ids: list[UUID] | None = Field(default=None, description="权限 ID 列表（全量替换）")
