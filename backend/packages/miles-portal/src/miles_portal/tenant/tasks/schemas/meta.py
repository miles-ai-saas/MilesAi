"""tasks 模块 GET */meta 响应体（与 tenant/tasks/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class TaskMetaOut(BaseModel):
    """任务状态与筛选项枚举。"""

    statuses: list[EnumOption] = Field(description="任务状态枚举选项")
    status_filters: list[EnumOption] = Field(description="任务状态筛选项")
    schema_version: str = Field(default=META_SCHEMA_VERSION, description="元数据 schema 版本")
