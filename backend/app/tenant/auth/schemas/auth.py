from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(description="用户名")
    password: str = Field(description="登录密码")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="刷新令牌")


class UserSessionOut(BaseModel):
    jti: str = Field(description="会话 ID（JWT jti）")
    user_agent: str | None = Field(default=None, description="客户端 User-Agent")
    ip: str | None = Field(default=None, description="登录 IP")
    created_at: str = Field(description="创建时间 ISO")
    last_seen_at: str | None = Field(default=None, description="最近活跃时间")
    is_current: bool = Field(default=False, description="是否为当前请求会话")


class TokenResponse(BaseModel):
    access_token: str = Field(description="访问令牌")
    refresh_token: str = Field(description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class UserInfo(BaseModel):
    id: UUID = Field(description="用户 ID")
    username: str = Field(description="用户名")
    email: EmailStr = Field(description="邮箱地址")
    tenant_id: UUID = Field(description="租户 ID")
    is_superuser: bool = Field(description="是否为超级管理员")
    permissions: list[str] = Field(description="权限编码列表")

    model_config = {"from_attributes": True}
