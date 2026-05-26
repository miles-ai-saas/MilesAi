"""monitor 模块 GET */meta 响应体（与 tenant/monitor/meta.py 字段一致）。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class MonitorMetaOut(BaseModel):
    """健康检查组件、整体状态与趋势天数枚举。"""

    health_components: list[EnumOption]
    overall_health_statuses: list[EnumOption]
    trend_day_ranges: list[EnumOption]
    schema_version: str = META_SCHEMA_VERSION
