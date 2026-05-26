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
    id: str
    label: str
    description: str | None = None
    active: bool = False


class ArchitectureKbRef(BaseModel):
    id: str
    name: str


class ArchitectureFlowRef(BaseModel):
    id: str
    name: str
    version: int
    status: str
    is_runtime_path: bool = False


class ArchitectureSubAgentRef(BaseModel):
    id: str
    name: str
    role_hint: str | None = None


class ArchitectureA2aPeerRef(BaseModel):
    id: str
    name: str
    role_hint: str | None = None
    enabled: bool = True


class ArchitectureModelRef(BaseModel):
    id: str
    name: str


class ArchitectureAttachments(BaseModel):
    model: ArchitectureModelRef | None = None
    kbs: list[ArchitectureKbRef] = Field(default_factory=list)
    sub_agents: list[ArchitectureSubAgentRef] = Field(default_factory=list)
    a2a_peers: list[ArchitectureA2aPeerRef] = Field(default_factory=list)
    flow: ArchitectureFlowRef | None = None


class AgentArchitectureOut(BaseModel):
    agent_id: str
    primary_path: PrimaryPath
    primary_path_label: str
    decision_steps: list[ArchitectureDecisionStep] = Field(default_factory=list)
    attachments: ArchitectureAttachments = Field(default_factory=ArchitectureAttachments)
    flow_graph: dict[str, Any] | None = Field(
        default=None,
        description="已绑定且存在发布版本时的 graph_json，供只读画布预览",
    )
