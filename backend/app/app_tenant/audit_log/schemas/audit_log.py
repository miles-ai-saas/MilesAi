from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TenantAuditLogOut(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    detail: dict
    created_at: datetime

    model_config = {"from_attributes": True}
