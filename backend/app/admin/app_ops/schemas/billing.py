from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.admin.models import BillStatus


class BillingPlanOut(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    price_monthly: Decimal
    max_knowledge_bases: int
    max_storage_mb: int
    max_tokens_monthly: int
    max_agents: int
    max_flows: int
    is_active: bool

    model_config = {"from_attributes": True}


class BillingPlanCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    price_monthly: Decimal = Decimal("0")
    max_knowledge_bases: int = 10
    max_storage_mb: int = 10240
    max_tokens_monthly: int = 1_000_000
    max_agents: int = 20
    max_flows: int = 20


class BillingPlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price_monthly: Decimal | None = None
    max_knowledge_bases: int | None = None
    max_storage_mb: int | None = None
    max_tokens_monthly: int | None = None
    max_agents: int | None = None
    max_flows: int | None = None
    is_active: bool | None = None


class BillLineItemOut(BaseModel):
    id: UUID
    item_type: str
    description: str | None
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal

    model_config = {"from_attributes": True}


class TenantBillOut(BaseModel):
    id: UUID
    tenant_id: UUID
    tenant_name: str | None = None
    plan_id: UUID | None
    period_start: date
    period_end: date
    amount: Decimal
    status: BillStatus
    tokens_used: int
    storage_used_mb: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantBillDetail(TenantBillOut):
    line_items: list[BillLineItemOut] = []
