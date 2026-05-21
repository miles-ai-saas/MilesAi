from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: UUID
    admin_id: UUID | None
    tenant_id: UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    detail: dict
    created_at: datetime

    model_config = {"from_attributes": True}
