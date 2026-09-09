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

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.models.model import ModelConfig


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
    current_flow_id: str | None = None  # 当前执行的流程 ID
    parent_flow_id: str | None = None  # SubFlow 父流程 ID
    parent_node_id: str | None = None  # SubFlow 父节点 ID
    subflow_depth: int = 0  # 子流程嵌套深度
    executing_node_id: str | None = None  # 当前执行节点（运行时注入）
    run_subflow: Callable[[dict[str, Any], "RunContext"], Awaitable["RunResult"]] | None = None  # 子流程执行回调（由 flow_runner 注入，避免节点层循环引用）
    # 画布 LLM 节点按 model_config_id 解析可用模型的回调（L1 注入；None 表示不支持）
    resolve_model: Callable[[str], Awaitable[ModelConfig]] | None = None
    # 画布 LLM 调用用量记录（L1 注入；None 表示不记录）
    usage_sink: Any = None
    # KB 检索能力载体（L1 注入；None 表示未装配，KnowledgeSearch 节点报错）
    kb_retrieval: Any = None
    # 生图/生视频模型解析回调（L1 注入；签名同
    # ``tenant.models.services.generative_model_resolve.resolve_{image,video}_gen_model``；
    # None 表示未装配，ImageGenerate/VideoGenerate 同步分支直接报错）
    resolve_generative_image: Callable[..., Awaitable[ModelConfig]] | None = None
    resolve_generative_video: Callable[..., Awaitable[ModelConfig]] | None = None


@dataclass
class RunResult:
    """流程单次 run 的终点输出与节点 steps 轨迹。"""

    output: Any  # 流程终点输出（文本或结构化）
    steps: list[dict[str, Any]] = field(default_factory=list)  # 节点执行步骤轨迹
