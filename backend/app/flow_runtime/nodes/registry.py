"""节点类型注册表 — 新增节点只需在此注册 handler。"""

from collections.abc import Awaitable, Callable
from typing import Any

from app.flow_runtime.nodes import rag_nodes, io_nodes, llm_nodes
from app.flow_runtime.types import RunContext

NodeHandler = Callable[[dict[str, Any], dict[str, Any], RunContext], Awaitable[Any]]

NODE_REGISTRY: dict[str, NodeHandler] = {
    "TextInput": io_nodes.text_input,
    "TextOutput": io_nodes.text_output,
    "KnowledgeSearch": rag_nodes.knowledge_search,
    "PromptTemplate": rag_nodes.prompt_template,
    "LLMCall": llm_nodes.llm_call,
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
    handler = NODE_REGISTRY.get(node_type)
    if not handler:
        raise ValueError(f"未知节点类型: {node_type}")
    return await handler(node_data, inputs, ctx)
