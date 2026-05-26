from pydantic import BaseModel, Field

from app.common.schemas.enum_meta import EnumOption


class GenerativeJobsMetaOut(BaseModel):
    statuses: list[EnumOption] = Field(description="任务状态")
    status_filters: list[EnumOption] = Field(description="列表筛选（含全部）")
    sources: list[EnumOption] = Field(description="任务来源")
    kinds: list[EnumOption] = Field(description="生成类型")
    schema_version: int = Field(description="元数据版本")
