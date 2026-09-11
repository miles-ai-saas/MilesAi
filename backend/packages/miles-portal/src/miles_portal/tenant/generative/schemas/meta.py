"""生成任务枚举元数据响应。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import EnumOption


# 生成任务元数据输出（状态、来源、类型选项）。
class GenerativeJobsMetaOut(BaseModel):
    statuses: list[EnumOption] = Field(description="任务状态")
    status_filters: list[EnumOption] = Field(description="列表筛选（含全部）")
    sources: list[EnumOption] = Field(description="任务来源")
    kinds: list[EnumOption] = Field(description="生成类型")
    schema_version: int = Field(description="元数据版本")
