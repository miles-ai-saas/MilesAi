"""flows 模块 GET */meta 响应体（与 tenant/flows/meta.py 字段一致）。"""

from app.common.schemas.enum_meta import EnumOption
from pydantic import BaseModel


class FlowMetaOut(BaseModel):
    """流程发布状态枚举。"""

    statuses: list[EnumOption]
