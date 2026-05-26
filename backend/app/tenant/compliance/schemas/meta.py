"""compliance 模块 GET */meta 响应体（与 tenant/compliance/meta.py 字段一致）。"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption
from pydantic import BaseModel


class ComplianceMetaOut(BaseModel):
    """敏感词策略与扫描模块枚举。"""

    sensitive_actions: list[EnumOption]
    scan_modules: list[EnumOption]
    schema_version: str = META_SCHEMA_VERSION
