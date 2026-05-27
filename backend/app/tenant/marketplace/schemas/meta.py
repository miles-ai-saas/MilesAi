"""marketplace 模块 GET */meta 响应体（与 tenant/marketplace/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class MarketplaceMetaOut(BaseModel):
    """应用上架状态与广场排序枚举。"""

    app_statuses: list[EnumOption] = Field(description="应用上架状态枚举")
    catalog_sorts: list[EnumOption] = Field(description="广场列表排序方式枚举")
    visibilities: list[EnumOption] = Field(description="应用可见范围枚举")
    review_mode: str = Field(default="platform", description="审核模式 platform|tenant|off")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本",
    )
