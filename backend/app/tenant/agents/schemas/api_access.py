"""智能体 API 对接（调试 Token）响应模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

DEBUG_TOKEN_WARNING = (
    "此令牌等效于当前登录用户凭据，请勿提交到代码仓库或分享；"
    "过期或登出相关会话后失效。正式对外请使用后续 API Key。"
)


class AgentDebugTokenOut(BaseModel):
    access_token: str = Field(description="调试 JWT，仅此响应返回明文")
    token_type: str = Field(default="bearer", description="固定 bearer")
    expires_in: int = Field(description="有效秒数")
    expires_at: datetime = Field(description="过期时间 UTC")
    agent_id: UUID = Field(description="智能体 ID")
    purpose: str = Field(default="agent_api_debug", description="令牌用途标记")
    warning: str = Field(description="安全提示")
