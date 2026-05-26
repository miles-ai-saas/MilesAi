"""智能体对话执行架构（与 AgentService.chat 路由一致）。"""

from typing import Any, Literal

from pydantic import BaseModel, Field

PrimaryPath = Literal[
    "a2a_host",
    "subagent_orchestration",
    "a2a_augmented",
    "flow",
    "tool_calling",
    "rag_graph",
    "rag_legacy",
    "rag_retrieve_only",
    "direct",
]

PRIMARY_PATH_LABELS: dict[str, str] = {
    "a2a_host": "A2A 宿主",
    "subagent_orchestration": "内部协同",
    "a2a_augmented": "A2A 增强",
    "flow": "编排流程",
    "tool_calling": "工具调用",
    "rag_graph": "LangGraph RAG",
    "rag_legacy": "线性 RAG",
    "rag_retrieve_only": "检索摘要",
    "direct": "直连大模型",
}


class ArchitectureDecisionStep(BaseModel):
    id: str = Field(description="决策步骤标识")
    label: str = Field(description="步骤展示名")
    description: str | None = Field(default=None, description="步骤说明")
    active: bool = Field(default=False, description="当前请求是否命中该步骤")


class ArchitectureKbRef(BaseModel):
    id: str = Field(description="知识库 ID")
    name: str = Field(description="知识库名称")


class ArchitectureFlowRef(BaseModel):
    id: str = Field(description="流程 ID")
    name: str = Field(description="流程名称")
    version: int = Field(description="当前发布/编辑版本号")
    status: str = Field(description="流程状态")
    is_runtime_path: bool = Field(
        default=False,
        description="是否为本次对话实际执行路径",
    )


class ArchitectureSubAgentRef(BaseModel):
    id: str = Field(description="子智能体 ID")
    name: str = Field(description="子智能体名称")
    role_hint: str | None = Field(default=None, description="角色提示")


class ArchitectureA2aPeerRef(BaseModel):
    id: str = Field(description="A2A 对端 ID")
    name: str = Field(description="对端名称")
    role_hint: str | None = Field(default=None, description="角色提示")
    enabled: bool = Field(default=True, description="绑定是否启用")


class ArchitectureModelRef(BaseModel):
    id: str = Field(description="模型配置 ID")
    name: str = Field(description="模型展示名")


class ArchitectureAttachments(BaseModel):
    model: ArchitectureModelRef | None = Field(default=None, description="绑定的大模型")
    kbs: list[ArchitectureKbRef] = Field(default_factory=list, description="绑定的知识库")
    sub_agents: list[ArchitectureSubAgentRef] = Field(
        default_factory=list,
        description="子智能体",
    )
    a2a_peers: list[ArchitectureA2aPeerRef] = Field(
        default_factory=list,
        description="A2A 对端",
    )
    flow: ArchitectureFlowRef | None = Field(default=None, description="绑定的流程")


class AgentArchitectureOut(BaseModel):
    agent_id: str = Field(description="智能体 ID")
    primary_path: PrimaryPath = Field(description="主执行路径标识")
    primary_path_label: str = Field(description="主执行路径展示名")
    decision_steps: list[ArchitectureDecisionStep] = Field(
        default_factory=list,
        description="路由决策步骤（用于架构图高亮）",
    )
    attachments: ArchitectureAttachments = Field(
        default_factory=ArchitectureAttachments,
        description="绑定的模型、知识库、流程等资源",
    )
    flow_graph: dict[str, Any] | None = Field(
        default=None,
        description="已绑定且存在发布版本时的 graph_json，供只读画布预览",
    )
