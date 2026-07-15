"""智能体 API 对接（调试 Token + 正式 API Key）响应模型。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

DEBUG_TOKEN_WARNING = (
    "此令牌等效于当前登录用户凭据，请勿提交到代码仓库或分享；"
    "过期或登出相关会话后失效。正式对外请使用 API Key。"
)

API_KEY_CREATED_WARNING = (
    "请立即复制并安全保存完整密钥；关闭后将无法再次查看明文。"
    "密钥不过期，可在工作台吊销。"
)

MAX_ACTIVE_AGENT_API_KEYS = 8


class AgentDebugTokenOut(BaseModel):
    access_token: str = Field(description="调试 JWT，仅此响应返回明文")
    token_type: str = Field(default="bearer", description="固定 bearer")
    expires_in: int = Field(description="有效秒数")
    expires_at: datetime = Field(description="过期时间 UTC")
    agent_id: UUID = Field(description="智能体 ID")
    purpose: str = Field(default="agent_api_debug", description="令牌用途标记")
    warning: str = Field(description="安全提示")


class AgentApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="密钥名称")


class AgentApiKeyOut(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    status: Literal["active", "revoked"]
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentApiKeyCreatedOut(AgentApiKeyOut):
    secret: str = Field(description="完整明文，仅创建时返回一次")
    warning: str = Field(description="安全提示")
