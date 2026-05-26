"""compliance 模块 GET */meta 响应体（与 tenant/compliance/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class ComplianceMetaOut(BaseModel):
    """敏感词策略与扫描模块枚举。"""

    sensitive_actions: list[EnumOption] = Field(description="敏感词命中处理策略枚举")
    scan_modules: list[EnumOption] = Field(description="扫描来源模块枚举")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本",
    )
