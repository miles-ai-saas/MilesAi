"""GET /flows/templates 响应体。"""

from typing import Any

from pydantic import BaseModel, Field


class FlowTemplateOut(BaseModel):
    id: str = Field(description="模板标识")
    label: str = Field(description="展示名称")
    hint: str = Field(description="简短说明")
    default_name: str = Field(description="建议的流程名称")
    insertable: bool = Field(
        default=True,
        description="是否可在编辑页「插入模板」",
    )
    graph_json: dict[str, Any] = Field(
        default_factory=dict,
        description="完整画布 graph_json",
    )


class FlowTemplatesOut(BaseModel):
    items: list[FlowTemplateOut] = Field(description="内置模板列表")
