from uuid import UUID

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    username: str = Field(description="管理员用户名")
    password: str = Field(description="登录密码")


class AdminTokenResponse(BaseModel):
    access_token: str = Field(description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class AdminInfo(BaseModel):
    id: UUID = Field(description="管理员 ID")
    username: str = Field(description="用户名")
    email: str | None = Field(description="邮箱")
    display_name: str | None = Field(description="显示名称")
    role: str = Field(description="角色")

    model_config = {"from_attributes": True}


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(description="当前密码")
    new_password: str = Field(..., min_length=6, description="新密码")


class AdminSessionOut(BaseModel):
    admin_id: UUID = Field(description="管理员 ID")
    username: str = Field(description="用户名")
    role: str = Field(description="角色")
    is_current: bool = Field(default=False, description="是否为当前登录会话")
    jti: str | None = Field(None, description="会话令牌 ID（JWT jti）")
