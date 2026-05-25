"""
画布节点类型 → 异步 handler 注册表。

RAG 相关
--------
- ``KnowledgeSearch`` / ``PromptTemplate`` → ``rag_nodes``（检索 + 模板）
- 常接在 ``TextInput`` 与 ``LLMCall`` 之间，等价于简化版 Agent 线性 RAG

新增节点：实现 ``(node_data, inputs, ctx) -> Any`` 并写入 ``NODE_REGISTRY``。
"""

from collections.abc import Awaitable, Callable
from typing import Any

from app.flow_runtime.nodes import control_nodes, io_nodes, llm_nodes, rag_nodes
from app.flow_runtime.types import RunContext

NodeHandler = Callable[[dict[str, Any], dict[str, Any], RunContext], Awaitable[Any]]

NODE_REGISTRY: dict[str, NodeHandler] = {
    "TextInput": io_nodes.text_input,
    "TextOutput": io_nodes.text_output,
    "KnowledgeSearch": rag_nodes.knowledge_search,  # ctx.kb_ids / node_data.kb_id
    "PromptTemplate": rag_nodes.prompt_template,
    "LLMCall": llm_nodes.llm_call,
    "ConditionBranch": control_nodes.condition_branch,
    "ParallelJoin": control_nodes.parallel_join,
    # 兼容历史 graph 中的节点类型别名
    "ChatInput": io_nodes.text_input,
    "ChatOutput": io_nodes.text_output,
}


async def execute_node(
    node_type: str,
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> Any:
    """按节点类型分发到已注册 handler（LangGraph 编译图内调用）。"""
    handler = NODE_REGISTRY.get(node_type)
    if not handler:
        raise ValueError(f"未知节点类型: {node_type}")
    return await handler(node_data, inputs, ctx)
