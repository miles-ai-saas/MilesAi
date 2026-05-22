from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.a2a.models import A2aPeerStatus


class A2aPeerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    base_url: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="外部 Agent 根地址或完整 Agent Card URL",
    )
    auth_config: dict = Field(default_factory=dict)


class A2aPeerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    base_url: str | None = Field(None, min_length=1, max_length=1024)
    auth_config: dict | None = None
    status: A2aPeerStatus | None = None


class A2aPeerOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    base_url: str | None
    agent_card_url: str
    card_display_name: str | None
    status: A2aPeerStatus
    skills_count: int = 0
    last_synced_at: datetime | None
    last_error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class A2aPeerSyncResult(BaseModel):
    peer: A2aPeerOut
    card_url: str
    message: str


class A2aPeerProbeResult(BaseModel):
    ok: bool
    card_url: str
    card_display_name: str | None = None
    skills_count: int = 0
    message: str
