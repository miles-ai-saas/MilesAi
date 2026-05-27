"""
画布节点类型 → 异步 handler 注册表。

RAG 相关
--------
- ``KnowledgeSearch`` / ``PromptTemplate`` → ``rag_nodes``（检索 + 模板）
- 常接在 ``TextInput`` 与 ``LLMCall`` 之间，等价于简化版 Agent 线性 RAG

合规 / 媒体 / 循环
------------------
- ``ComplianceCheck`` → ``compliance_nodes``（敏感词扫描，warn/block 模式）
- ``OcrExtract`` / ``AudioTranscribe`` → ``media_nodes``（附件 OCR / 音频转写）
- ``LoopNode`` → ``loop_nodes``（循环执行 SubFlow，支持条件退出）

新增节点：实现 ``(node_data, inputs, ctx) -> Any`` 并写入 ``NODE_REGISTRY``。
"""

from collections.abc import Awaitable, Callable
from typing import Any

from app.flow_runtime.constants import CanvasNodeType, parse_canvas_node_type
from app.flow_runtime.nodes import (
    compliance_nodes,
    control_nodes,
    grade_nodes,
    image_generate,
    video_generate,
    io_nodes,
    llm_nodes,
    loop_nodes,
    media_nodes,
    rag_nodes,
    subflow_nodes,
    tool_nodes,
)
from app.flow_runtime.types import RunContext

NodeHandler = Callable[[dict[str, Any], dict[str, Any], RunContext], Awaitable[Any]]

NODE_REGISTRY: dict[str, NodeHandler] = {
    CanvasNodeType.TEXT_INPUT: io_nodes.text_input,
    CanvasNodeType.TEXT_OUTPUT: io_nodes.text_output,
    CanvasNodeType.KNOWLEDGE_SEARCH: rag_nodes.knowledge_search,
    CanvasNodeType.PROMPT_TEMPLATE: rag_nodes.prompt_template,
    CanvasNodeType.LLM_CALL: llm_nodes.llm_call,
    CanvasNodeType.IMAGE_GENERATE: image_generate.image_generate,
    CanvasNodeType.VIDEO_GENERATE: video_generate.video_generate,
    CanvasNodeType.PLATFORM_TOOL: tool_nodes.platform_tool,
    CanvasNodeType.CONDITION: control_nodes.condition_branch,
    CanvasNodeType.RELEVANCE_GRADE: grade_nodes.relevance_grade,
    CanvasNodeType.STATIC_RESPONSE: io_nodes.static_response,
    CanvasNodeType.PARALLEL_JOIN: control_nodes.parallel_join,
    CanvasNodeType.CHAT_INPUT: io_nodes.text_input,
    CanvasNodeType.CHAT_OUTPUT: io_nodes.text_output,
    CanvasNodeType.SUB_FLOW: subflow_nodes.sub_flow,
    CanvasNodeType.LOOP: loop_nodes.loop_node,
    CanvasNodeType.COMPLIANCE_CHECK: compliance_nodes.compliance_check,
    CanvasNodeType.OCR_EXTRACT: media_nodes.ocr_extract,
    CanvasNodeType.AUDIO_TRANSCRIBE: media_nodes.audio_transcribe,
}


async def execute_node(
    node_type: str,
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> Any:
    """按节点类型分发到已注册 handler（LangGraph 编译图内调用）。"""
    parse_canvas_node_type(node_type)
    handler = NODE_REGISTRY.get(node_type)
    if not handler:
        raise ValueError(f"未知节点类型: {node_type}")
    return await handler(node_data, inputs, ctx)
