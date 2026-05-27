from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


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
    user_ids: list[UUID] = Field(..., min_length=1, description="待禁用用户 ID 列表")


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
