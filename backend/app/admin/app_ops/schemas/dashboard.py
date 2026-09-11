"""运营控制台汇总统计 DTO。"""

from pydantic import BaseModel, Field


# 控制台概览卡片指标。
class AdminDashboardSummaryOut(BaseModel):
    tenants_total: int = Field(description="租户总数")
    tenants_active: int = Field(description="活跃租户数")
    risk_open: int = Field(description="未处理风险事件")
    bills_total: int = Field(description="账单总数")
    bills_issued_month: int = Field(description="本月已出账单数")
    audit_today: int = Field(description="今日审计条数")
    plans_active: int = Field(description="启用中套餐数")
