"""GET /flows/templates 响应体。"""

from typing import Any

from pydantic import BaseModel, Field


class FlowTemplateOut(BaseModel):
    id: str
    label: str
    hint: str
    default_name: str
    insertable: bool = True
    graph_json: dict[str, Any] = Field(default_factory=dict)


class FlowTemplatesOut(BaseModel):
    items: list[FlowTemplateOut]
