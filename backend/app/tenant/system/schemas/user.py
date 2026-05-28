from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    email: EmailStr = Field(description="邮箱地址")
    password: str = Field(..., min_length=6, description="登录密码")
    phone: str | None = Field(default=None, description="手机号")
    tenant_id: UUID | None = Field(default=None, description="所属租户 ID")
    role_ids: list[UUID] = Field(default_factory=list, description="角色 ID 列表")


class UserUpdate(BaseModel):
    email: EmailStr | None = Field(default=None, description="邮箱地址")
    phone: str | None = Field(default=None, description="手机号")
    is_active: bool | None = Field(default=None, description="是否启用")
    role_ids: list[UUID] | None = Field(default=None, description="角色 ID 列表（全量替换）")


class UserResetPassword(BaseModel):
    password: str = Field(..., min_length=6, description="新登录密码")


class UserBatchDeactivate(BaseModel):
    user_ids: list[UUID] = Field(..., min_length=1, description="待删除用户 ID 列表")


class UserBatchRequest(BaseModel):
    user_ids: list[UUID] = Field(..., min_length=1, description="目标用户 ID 列表")
    action: Literal["enable", "disable", "assign_roles", "deactivate"] = Field(description="enable/disable 仅改状态；assign_roles 批量赋角色；deactivate 软删")
    role_ids: list[UUID] | None = Field(
        default=None,
        description="action=assign_roles 时必填，写入各用户角色（全量替换）",
    )

    @model_validator(mode="after")
    def _validate_roles(self) -> "UserBatchRequest":
        if self.action == "assign_roles" and not self.role_ids:
            raise ValueError("assign_roles 需要提供 role_ids")
        return self


class UserOut(BaseModel):
    id: UUID = Field(description="用户 ID")
    username: str = Field(description="用户名")
    email: EmailStr = Field(description="邮箱地址")
    phone: str | None = Field(default=None, description="手机号")
    tenant_id: UUID = Field(description="租户 ID")
    is_active: bool = Field(description="是否启用")
    is_superuser: bool = Field(description="是否为超级管理员")
    role_codes: list[str] = Field(default_factory=list, description="角色编码列表")

    model_config = {"from_attributes": True}
