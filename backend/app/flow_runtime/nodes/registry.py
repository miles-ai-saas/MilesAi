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

from app.flow_runtime.constants import (
    CHAT_INPUT_NODE_TYPE,
    CHAT_OUTPUT_NODE_TYPE,
    CONDITION_NODE_TYPE,
    KNOWLEDGE_SEARCH_NODE_TYPE,
    LLM_CALL_NODE_TYPE,
    IMAGE_GENERATE_NODE_TYPE,
    VIDEO_GENERATE_NODE_TYPE,
    PARALLEL_JOIN_NODE_TYPE,
    PLATFORM_TOOL_NODE_TYPE,
    PROMPT_TEMPLATE_NODE_TYPE,
    RELEVANCE_GRADE_NODE_TYPE,
    STATIC_RESPONSE_NODE_TYPE,
    TEXT_INPUT_NODE_TYPE,
    TEXT_OUTPUT_NODE_TYPE,
)
from app.flow_runtime.nodes import (
    control_nodes,
    grade_nodes,
    image_generate,
    video_generate,
    io_nodes,
    llm_nodes,
    rag_nodes,
    tool_nodes,
)
from app.flow_runtime.types import RunContext

NodeHandler = Callable[[dict[str, Any], dict[str, Any], RunContext], Awaitable[Any]]

NODE_REGISTRY: dict[str, NodeHandler] = {
    TEXT_INPUT_NODE_TYPE: io_nodes.text_input,
    TEXT_OUTPUT_NODE_TYPE: io_nodes.text_output,
    KNOWLEDGE_SEARCH_NODE_TYPE: rag_nodes.knowledge_search,
    PROMPT_TEMPLATE_NODE_TYPE: rag_nodes.prompt_template,
    LLM_CALL_NODE_TYPE: llm_nodes.llm_call,
    IMAGE_GENERATE_NODE_TYPE: image_generate.image_generate,
    VIDEO_GENERATE_NODE_TYPE: video_generate.video_generate,
    PLATFORM_TOOL_NODE_TYPE: tool_nodes.platform_tool,
    CONDITION_NODE_TYPE: control_nodes.condition_branch,
    RELEVANCE_GRADE_NODE_TYPE: grade_nodes.relevance_grade,
    STATIC_RESPONSE_NODE_TYPE: io_nodes.static_response,
    PARALLEL_JOIN_NODE_TYPE: control_nodes.parallel_join,
    CHAT_INPUT_NODE_TYPE: io_nodes.text_input,
    CHAT_OUTPUT_NODE_TYPE: io_nodes.text_output,
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
