"""
流程运行时 DTO（画布 ↔ 后端执行）。

``RunContext``
--------------
- ``inputs``：入口变量（如 ``query``），各节点从上游边汇聚的 ``inputs`` 读取
- ``kb_ids``：Agent 绑定知识库 id 列表（字符串），供 KnowledgeSearch 默认检索范围
- ``model_config_id`` / ``system_prompt``：LLMCall 与 PromptTemplate 前缀

与 Agent 对话关系：``AgentService.chat`` 发布流程时构造 ``RunContext`` 并 ``get_flow_runtime().run``。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowGraph:
    """nodes + edges，与前端画布导出结构一致。"""
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, data: dict) -> "FlowGraph":
        """从前端导出的 graph_json 构造。"""
        return cls(
            nodes=data.get("nodes") or [],
            edges=data.get("edges") or [],
        )


@dataclass
class RunContext:
    """单次执行注入：inputs 为入口变量，kb_ids/model 供 RAG/LLM 节点读取。"""

    tenant_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    kb_ids: list[str] = field(default_factory=list)
    model_config_id: str | None = None
    system_prompt: str | None = None
    user_id: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)
    is_superuser: bool = False
    agent_id: str | None = None
    agent_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    output: Any
    steps: list[dict[str, Any]] = field(default_factory=list)
