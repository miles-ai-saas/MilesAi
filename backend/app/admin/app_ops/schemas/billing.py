from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.admin.models import BillStatus


class BillingPlanOut(BaseModel):
    id: UUID = Field(description="计费方案 ID")
    code: str = Field(description="方案编码")
    name: str = Field(description="方案名称")
    description: str | None = Field(description="方案描述")
    price_monthly: Decimal = Field(description="月费价格")
    max_knowledge_bases: int = Field(description="知识库数量上限")
    max_storage_mb: int = Field(description="存储空间上限（MB）")
    max_tokens_monthly: int = Field(description="每月 Token 用量上限")
    max_agents: int = Field(description="智能体数量上限")
    max_flows: int = Field(description="工作流数量上限")
    is_active: bool = Field(description="是否启用")

    model_config = {"from_attributes": True}


class BillingPlanCreate(BaseModel):
    code: str = Field(description="方案编码")
    name: str = Field(description="方案名称")
    description: str | None = Field(None, description="方案描述")
    price_monthly: Decimal = Field(default=Decimal("0"), description="月费价格")
    max_knowledge_bases: int = Field(default=10, description="知识库数量上限")
    max_storage_mb: int = Field(default=10240, description="存储空间上限（MB）")
    max_tokens_monthly: int = Field(default=1_000_000, description="每月 Token 用量上限")
    max_agents: int = Field(default=20, description="智能体数量上限")
    max_flows: int = Field(default=20, description="工作流数量上限")


class BillingPlanUpdate(BaseModel):
    name: str | None = Field(None, description="方案名称")
    description: str | None = Field(None, description="方案描述")
    price_monthly: Decimal | None = Field(None, description="月费价格")
    max_knowledge_bases: int | None = Field(None, description="知识库数量上限")
    max_storage_mb: int | None = Field(None, description="存储空间上限（MB）")
    max_tokens_monthly: int | None = Field(None, description="每月 Token 用量上限")
    max_agents: int | None = Field(None, description="智能体数量上限")
    max_flows: int | None = Field(None, description="工作流数量上限")
    is_active: bool | None = Field(None, description="是否启用")


class BillLineItemOut(BaseModel):
    id: UUID = Field(description="账单明细项 ID")
    item_type: str = Field(description="明细类型")
    description: str | None = Field(description="明细描述")
    quantity: Decimal = Field(description="数量")
    unit_price: Decimal = Field(description="单价")
    amount: Decimal = Field(description="金额")

    model_config = {"from_attributes": True}


class TenantBillOut(BaseModel):
    id: UUID = Field(description="账单 ID")
    tenant_id: UUID = Field(description="租户 ID")
    tenant_name: str | None = Field(None, description="租户名称")
    plan_id: UUID | None = Field(description="计费方案 ID")
    period_start: date = Field(description="账期开始日期")
    period_end: date = Field(description="账期结束日期")
    amount: Decimal = Field(description="账单总金额")
    status: BillStatus = Field(description="账单状态")
    tokens_used: int = Field(description="本期 Token 用量")
    storage_used_mb: int = Field(description="本期存储用量（MB）")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


class TenantBillDetail(TenantBillOut):
    line_items: list[BillLineItemOut] = Field(default=[], description="账单明细列表")


class TenantBillStatusUpdate(BaseModel):
    status: BillStatus = Field(description="目标状态（paid / void）")
