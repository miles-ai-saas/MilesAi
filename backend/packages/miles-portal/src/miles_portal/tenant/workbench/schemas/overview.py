"""工作台概览统计 schema。"""

from pydantic import BaseModel, Field


class WorkbenchOverviewOut(BaseModel):
    """工作台概览统计（单次聚合，避免多路列表接口）。"""

    agents: int = Field(0, description="智能体数量")
    kbs: int = Field(0, description="知识库数量")
    flows: int = Field(0, description="流程数量")
    prompts: int = Field(0, description="提示词模版数量")
    models: int = Field(0, description="可用模型配置数量（内置已发布 + 租户自定义）")
    tasks: int = Field(0, description="任务记录数量")
