"""租户资源配额只读视图。"""

from pydantic import BaseModel, Field


class QuotaMetricOut(BaseModel):
    used: int = Field(description="已用量")
    max: int = Field(description="上限；0 表示不限")
    unit: str = Field(default="", description="单位说明，如 MB、次")


class TenantQuotaOut(BaseModel):
    knowledge_bases: QuotaMetricOut
    storage_mb: QuotaMetricOut
    agents: QuotaMetricOut
    flows: QuotaMetricOut
    tokens_monthly: QuotaMetricOut
    generative_daily: QuotaMetricOut = Field(description="生图/生视频当日次数")
