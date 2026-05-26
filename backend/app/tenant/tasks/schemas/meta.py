"""tasks 模块 GET */meta 响应体（与 tenant/tasks/meta.py 字段一致）。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import EnumOption


class TaskMetaOut(BaseModel):
    """任务状态与筛选项枚举。"""

    statuses: list[EnumOption]
    status_filters: list[EnumOption]
    schema_version: str = "1"
