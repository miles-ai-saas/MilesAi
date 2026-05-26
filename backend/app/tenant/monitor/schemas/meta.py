"""monitor 模块 GET */meta 响应体（与 tenant/monitor/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class MonitorMetaOut(BaseModel):
    """健康检查组件、整体状态与趋势天数枚举。"""

    health_components: list[EnumOption] = Field(description="健康检查组件枚举")
    overall_health_statuses: list[EnumOption] = Field(description="整体健康状态枚举")
    trend_day_ranges: list[EnumOption] = Field(description="趋势图天数范围枚举")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本",
    )
