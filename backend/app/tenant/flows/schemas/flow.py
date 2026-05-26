from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.common.schemas.media import MediaRefIn
from app.models.flow import FlowStatus
from app.tenant.tags.schemas.tag import TagRefOut


class FlowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    tag_ids: list[UUID] = []
    graph_json: dict = Field(default_factory=lambda: {"nodes": [], "edges": []})


class FlowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tag_ids: list[UUID] | None = None


class FlowSaveGraph(BaseModel):
    graph_json: dict
    remark: str | None = None


class FlowVersionSummaryOut(BaseModel):
    id: UUID
    flow_id: UUID
    version: int
    editor_id: UUID | None
    remark: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FlowVersionOut(BaseModel):
    id: UUID
    flow_id: UUID
    version: int
    graph_json: dict
    editor_id: UUID | None
    remark: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FlowOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    tags: list[TagRefOut] = []
    status: FlowStatus
    current_version: int
    created_at: datetime


class FlowRunRequest(BaseModel):
    inputs: dict = Field(default_factory=dict)
    media: list[MediaRefIn] = Field(
        default_factory=list,
        description="调试运行附图（LLMCall vision，服务端读附件转 data URL）",
    )
    kb_ids: list[UUID] = Field(
        default_factory=list,
        description="调试运行注入 KnowledgeSearch（节点未配置 kb_id 时使用）",
    )
    use_langgraph: bool = Field(
        True,
        description="已废弃：画布统一由 LangGraph 执行，保留字段仅为兼容旧客户端",
    )

    @model_validator(mode="after")
    def validate_inputs_or_media(self) -> "FlowRunRequest":
        q = str(
            self.inputs.get("query")
            or self.inputs.get("message")
            or self.inputs.get("input")
            or ""
        ).strip()
        if not q and not self.media:
            raise ValueError("inputs 需包含 query（或 message/input），或提供 media 附图")
        return self


class FlowCompileErrorDetail(BaseModel):
    code: str
    message: str
    node_id: str | None = None


class FlowCompileReport(BaseModel):
    compilable: bool
    engine: str
    node_order: list[str] = []
    node_types: list[str] = []
    execution_layers: list[list[str]] = []
    parallel_groups: list[list[str]] = []
    conditional_nodes: list[str] = []
    errors: list[str] = []
    error_details: list[FlowCompileErrorDetail] = []


class FlowRunResponse(BaseModel):
    output: str | dict | list | None
    steps: list[dict] = []
