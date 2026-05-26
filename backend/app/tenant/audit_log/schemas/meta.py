"""audit_log 模块 GET */meta 响应体（与 tenant/audit_log/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class AuditMetaOut(BaseModel):
    """审计列表筛选与列展示文案。"""

    resource_types: list[EnumOption] = Field(description="资源类型列展示枚举")
    resource_type_filters: list[EnumOption] = Field(
        description="资源类型筛选项枚举（首项可为空=全部）",
    )
    action_filters: list[EnumOption] = Field(description="操作动作筛选项枚举")
    action_labels: list[EnumOption] = Field(
        description="操作动作展示文案（未知 action 回退原值）",
    )
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本",
    )
