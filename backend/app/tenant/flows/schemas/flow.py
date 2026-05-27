from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.common.schemas.media import MediaRefIn
from app.models.flow import FlowStatus
from app.tenant.tags.schemas.tag import TagRefOut


class FlowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="流程名称")
    description: str | None = Field(default=None, description="描述")
    tag_ids: list[UUID] = Field(default_factory=list, description="标签 ID 列表")
    graph_json: dict = Field(
        default_factory=lambda: {"nodes": [], "edges": []},
        description="初始画布 graph_json",
    )


class FlowUpdate(BaseModel):
    name: str | None = Field(default=None, description="流程名称")
    description: str | None = Field(default=None, description="描述")
    tag_ids: list[UUID] | None = Field(default=None, description="标签 ID 列表（全量替换）")


class FlowSaveGraph(BaseModel):
    graph_json: dict = Field(description="画布 graph_json")
    remark: str | None = Field(default=None, description="版本备注")


class FlowVersionSummaryOut(BaseModel):
    id: UUID = Field(description="版本记录 ID")
    flow_id: UUID = Field(description="流程 ID")
    version: int = Field(description="版本号")
    editor_id: UUID | None = Field(default=None, description="保存者用户 ID")
    remark: str | None = Field(default=None, description="版本备注")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


class FlowVersionOut(BaseModel):
    id: UUID = Field(description="版本记录 ID")
    flow_id: UUID = Field(description="流程 ID")
    version: int = Field(description="版本号")
    graph_json: dict = Field(description="完整画布 graph_json")
    editor_id: UUID | None = Field(default=None, description="保存者用户 ID")
    remark: str | None = Field(default=None, description="版本备注")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


class FlowOut(BaseModel):
    id: UUID = Field(description="流程 ID")
    tenant_id: UUID = Field(description="租户 ID")
    name: str = Field(description="流程名称")
    description: str | None = Field(default=None, description="描述")
    tags: list[TagRefOut] = Field(default_factory=list, description="标签列表")
    status: FlowStatus = Field(description="发布状态")
    current_version: int = Field(description="当前版本号")
    created_at: datetime = Field(description="创建时间")


class FlowRunRequest(BaseModel):
    inputs: dict = Field(
        default_factory=dict,
        description="运行时输入变量（如 query）",
    )
    media: list[MediaRefIn] = Field(
        default_factory=list,
        description="调试运行附图（LLMCall vision，服务端读附件转 data URL）",
    )
    kb_ids: list[UUID] = Field(
        default_factory=list,
        description="调试运行注入 KnowledgeSearch（节点未配置 kb_id 时使用）",
    )
    async_generative: bool = Field(
        default=True,
        description="含生视频节点时提交异步任务（False 则同步等待，可能阻塞数分钟）",
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
    code: str = Field(description="错误码")
    message: str = Field(description="错误说明")
    node_id: str | None = Field(default=None, description="关联节点 ID")


class FlowCompileReport(BaseModel):
    compilable: bool = Field(description="是否可编译执行")
    engine: str = Field(description="执行引擎标识")
    node_order: list[str] = Field(default_factory=list, description="拓扑排序后的节点 ID")
    node_types: list[str] = Field(default_factory=list, description="节点类型列表（与 node_order 对齐）")
    execution_layers: list[list[str]] = Field(
        default_factory=list,
        description="分层执行计划",
    )
    parallel_groups: list[list[str]] = Field(
        default_factory=list,
        description="可并行执行的节点组",
    )
    conditional_nodes: list[str] = Field(
        default_factory=list,
        description="含条件出边的节点 ID",
    )
    errors: list[str] = Field(default_factory=list, description="错误摘要列表")
    error_details: list[FlowCompileErrorDetail] = Field(
        default_factory=list,
        description="结构化错误详情",
    )


class FlowRunResponse(BaseModel):
    output: str | dict | list | None = Field(description="流程终点输出")
    steps: list[dict] = Field(default_factory=list, description="节点执行步骤轨迹")
