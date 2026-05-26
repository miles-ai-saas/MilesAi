"""
流程运行时 DTO（画布 ↔ 后端执行）。

``RunContext``
--------------
- ``inputs``：入口变量（如 ``query``），各节点从上游边汇聚的 ``inputs`` 读取
- ``kb_ids``：Agent 绑定知识库 id 列表（字符串），供 KnowledgeSearch 默认检索范围
- ``model_config_id`` / ``system_prompt``：LLMCall 与 PromptTemplate 前缀
- ``media``：调试/对话注入的附图 ``[{attachment_id, detail}]``，供 ``LLMCall`` vision

与 Agent 对话关系：``AgentService.chat`` 发布流程时构造 ``RunContext`` 并 ``get_flow_runtime().run``。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowGraph:
    """nodes + edges，与前端画布导出结构一致。"""

    nodes: list[dict[str, Any]]  # 画布节点列表
    edges: list[dict[str, Any]]  # 节点连线列表

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

    tenant_id: str  # 租户 ID
    inputs: dict[str, Any] = field(default_factory=dict)  # 入口变量（如 query）
    variables: dict[str, Any] = field(default_factory=dict)  # 运行期中间变量
    kb_ids: list[str] = field(default_factory=list)  # 默认检索知识库 ID 列表
    model_config_id: str | None = None  # 默认大模型配置 ID
    system_prompt: str | None = None  # 系统提示词前缀
    user_id: str | None = None  # 触发运行的用户 ID
    permissions: frozenset[str] = field(default_factory=frozenset)  # 用户权限码
    is_superuser: bool = False  # 是否超级用户
    agent_id: str | None = None  # 绑定智能体 ID（工具/技能鉴权用）
    agent_config: dict[str, Any] = field(default_factory=dict)  # 智能体扩展配置
    media: list[dict[str, Any]] = field(default_factory=list)  # 附图 [{attachment_id, detail}]
    generative_video_async: bool = True  # False 时 VideoGenerate 节点同步阻塞
    generative_image_async: bool = True  # False 时 ImageGenerate 节点同步阻塞


@dataclass
class RunResult:
    output: Any  # 流程终点输出（文本或结构化）
    steps: list[dict[str, Any]] = field(default_factory=list)  # 节点执行步骤轨迹
