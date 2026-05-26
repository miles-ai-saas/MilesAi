"""marketplace 模块 GET */meta 响应体（与 tenant/marketplace/meta.py 字段一致）。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import EnumOption


class MarketplaceMetaOut(BaseModel):
    """应用上架状态与广场排序枚举。"""

    app_statuses: list[EnumOption]
    catalog_sorts: list[EnumOption]
    schema_version: str = "1"
