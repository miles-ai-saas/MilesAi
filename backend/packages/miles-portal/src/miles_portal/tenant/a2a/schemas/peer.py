"""
A2A Peer HTTP 请求/响应模型。

``base_url`` 可为 Agent 根地址或完整 Card URL；同步后 ``agent_card_url`` 规范化。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from miles_portal.tenant.a2a.models import A2aPeerStatus


# 创建外部 A2A 对端的入参。
class A2aPeerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="对端名称")
    description: str | None = Field(default=None, description="对端描述")
    base_url: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="外部 Agent 根地址或完整 Agent Card URL",
    )
    auth_config: dict = Field(default_factory=dict, description="认证配置 JSON")


# 更新外部 A2A 对端的入参；字段均可选。
class A2aPeerUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="对端名称",
    )
    description: str | None = Field(default=None, description="对端描述")
    base_url: str | None = Field(
        default=None,
        min_length=1,
        max_length=1024,
        description="外部 Agent 根地址或 Agent Card URL",
    )
    auth_config: dict | None = Field(default=None, description="认证配置 JSON")
    status: A2aPeerStatus | None = Field(default=None, description="连接状态")


# 外部 A2A 对端详情（含 Agent Card 展示名与技能数）。
class A2aPeerOut(BaseModel):
    id: UUID = Field(description="对端 ID")
    tenant_id: UUID = Field(description="租户 ID")
    name: str = Field(description="对端名称")
    description: str | None = Field(default=None, description="对端描述")
    base_url: str | None = Field(default=None, description="用户配置的根地址")
    agent_card_url: str = Field(description="规范化后的 Agent Card URL")
    card_display_name: str | None = Field(default=None, description="Agent Card 展示名")
    status: A2aPeerStatus = Field(description="连接状态")
    skills_count: int = Field(default=0, description="Card 中技能数量")
    last_synced_at: datetime | None = Field(default=None, description="上次同步时间")
    last_error: str | None = Field(default=None, description="上次同步错误信息")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# 同步 Agent Card 的结果：对端详情、实际 URL 与说明。
class A2aPeerSyncResult(BaseModel):
    peer: A2aPeerOut = Field(description="同步后的对端详情")
    card_url: str = Field(description="使用的 Agent Card URL")
    message: str = Field(description="同步结果说明")


# 探测外部 Agent Card 的结果（不落库、不改对端状态）。
class A2aPeerProbeResult(BaseModel):
    ok: bool = Field(description="探测是否成功")
    card_url: str = Field(description="探测使用的 Card URL")
    card_display_name: str | None = Field(default=None, description="Card 展示名")
    skills_count: int = Field(default=0, description="Card 中技能数量")
    message: str = Field(description="探测结果说明")
