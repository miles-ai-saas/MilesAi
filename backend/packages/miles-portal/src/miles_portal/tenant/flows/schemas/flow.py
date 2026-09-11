"""流程（Flow）HTTP 请求/响应模型：画布、版本、发布、调试运行与编译报告。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from miles_common.schemas.media import MediaRefIn
from miles_core.models.flow import FlowStatus
from miles_portal.tenant.tags.schemas.tag import TagRefOut


# 创建流程的入参，可携带初始画布。
class FlowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="流程名称")
    description: str | None = Field(default=None, description="描述")
    tag_ids: list[UUID] = Field(default_factory=list, description="标签 ID 列表")
    graph_json: dict = Field(
        default_factory=lambda: {"nodes": [], "edges": []},
        description="初始画布 graph_json",
    )


# 更新流程元信息的入参；标签为全量替换。
class FlowUpdate(BaseModel):
    name: str | None = Field(default=None, description="流程名称")
    description: str | None = Field(default=None, description="描述")
    tag_ids: list[UUID] | None = Field(default=None, description="标签 ID 列表（全量替换）")


# 保存画布入参；每次保存递增版本号。
class FlowSaveGraph(BaseModel):
    graph_json: dict = Field(description="画布 graph_json")
    remark: str | None = Field(default=None, description="版本备注")


# 流程版本摘要（不含 graph_json）。
class FlowVersionSummaryOut(BaseModel):
    id: UUID = Field(description="版本记录 ID")
    flow_id: UUID = Field(description="流程 ID")
    version: int = Field(description="版本号")
    editor_id: UUID | None = Field(default=None, description="保存者用户 ID")
    remark: str | None = Field(default=None, description="版本备注")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# 流程版本详情（含完整 graph_json）。
class FlowVersionOut(BaseModel):
    id: UUID = Field(description="版本记录 ID")
    flow_id: UUID = Field(description="流程 ID")
    version: int = Field(description="版本号")
    graph_json: dict = Field(description="完整画布 graph_json")
    editor_id: UUID | None = Field(default=None, description="保存者用户 ID")
    remark: str | None = Field(default=None, description="版本备注")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# 流程列表/详情输出。
class FlowOut(BaseModel):
    id: UUID = Field(description="流程 ID")
    tenant_id: UUID = Field(description="租户 ID")
    name: str = Field(description="流程名称")
    description: str | None = Field(default=None, description="描述")
    tags: list[TagRefOut] = Field(default_factory=list, description="标签列表")
    status: FlowStatus = Field(description="发布状态")
    current_version: int = Field(description="当前版本号")
    created_at: datetime = Field(description="创建时间")


# 工作台调试运行入参；含生视频节点时可选异步提交。
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
        """要求 inputs 含 query/message/input，或至少提供一张附图。"""

        q = str(self.inputs.get("query") or self.inputs.get("message") or self.inputs.get("input") or "").strip()
        if not q and not self.media:
            raise ValueError("inputs 需包含 query（或 message/input），或提供 media 附图")
        return self


# 单条编译错误详情。
class FlowCompileErrorDetail(BaseModel):
    code: str = Field(description="错误码")
    message: str = Field(description="错误说明")
    node_id: str | None = Field(default=None, description="关联节点 ID")


# LangGraph 编译预览报告（拓扑序、分层、错误）。
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


# 调试运行输出（终点输出 + 节点执行轨迹）。
class FlowRunResponse(BaseModel):
    output: str | dict | list | None = Field(description="流程终点输出")
    steps: list[dict] = Field(default_factory=list, description="节点执行步骤轨迹")
