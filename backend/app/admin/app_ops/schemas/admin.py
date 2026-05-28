from uuid import UUID

from pydantic import BaseModel, Field

ADMIN_ROLES = frozenset({"super_admin", "ops", "billing", "security", "viewer", "operator"})


class PlatformAdminOut(BaseModel):
    id: UUID = Field(description="管理员 ID")
    username: str = Field(description="用户名")
    email: str | None = Field(description="邮箱")
    display_name: str | None = Field(description="显示名称")
    role: str = Field(description="角色")
    is_active: bool = Field(description="是否启用")

    model_config = {"from_attributes": True}


class PlatformAdminCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64, description="用户名")
    password: str = Field(min_length=6, description="初始密码")
    email: str | None = Field(None, description="邮箱")
    display_name: str | None = Field(None, description="显示名称")
    role: str = Field(default="ops", description="角色")


class PlatformAdminUpdate(BaseModel):
    email: str | None = Field(None, description="邮箱")
    display_name: str | None = Field(None, description="显示名称")
    role: str | None = Field(None, description="角色")
    is_active: bool | None = Field(None, description="是否启用")


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6, description="新密码")
