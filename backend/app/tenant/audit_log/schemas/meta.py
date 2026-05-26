"""audit_log 模块 GET */meta 响应体（与 tenant/audit_log/meta.py 字段一致）。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class AuditMetaOut(BaseModel):
    """审计列表筛选与列展示文案。"""

    resource_types: list[EnumOption]  # 列展示（无空值）
    resource_type_filters: list[EnumOption]  # 筛选下拉（首项可为空=全部）
    action_filters: list[EnumOption]
    action_labels: list[EnumOption]  # 未知 action 回退原值
    schema_version: str = META_SCHEMA_VERSION
