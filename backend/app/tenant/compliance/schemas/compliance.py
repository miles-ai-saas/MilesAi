from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.compliance.models import SensitiveAction


class SensitiveWordCreate(BaseModel):
    word: str = Field(..., min_length=1, max_length=128)
    category: str | None = None
    action: SensitiveAction = SensitiveAction.WARN


class SensitiveWordBatchCreate(BaseModel):
    words: list[SensitiveWordCreate] = Field(..., min_length=1, max_length=200)


class SensitiveWordUpdate(BaseModel):
    category: str | None = None
    action: SensitiveAction | None = None
    is_active: bool | None = None


class ComplianceScanRequest(BaseModel):
    text: str = Field(..., min_length=1)
    module: str = "manual_test"


class ComplianceScanMatch(BaseModel):
    word: str
    action: SensitiveAction


class ComplianceScanResult(BaseModel):
    blocked: bool
    warned: bool
    matches: list[ComplianceScanMatch]


class SensitiveWordOut(BaseModel):
    id: UUID
    tenant_id: UUID
    word: str
    category: str | None
    action: SensitiveAction
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InterceptLogOut(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID | None
    module: str
    direction: str
    matched_word: str | None
    action: SensitiveAction
    content_snippet: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
