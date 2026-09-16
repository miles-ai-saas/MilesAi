"""画布节点类型（registry、LangGraph 编译与分析共用）。"""

from __future__ import annotations

import enum


class CanvasNodeType(enum.StrEnum):
    """React Flow ``node.type`` 与 ``NODE_REGISTRY`` 键名。"""

    TEXT_INPUT = "TextInput"
    TEXT_OUTPUT = "TextOutput"
    KNOWLEDGE_SEARCH = "KnowledgeSearch"
    PROMPT_TEMPLATE = "PromptTemplate"
    LLM_CALL = "LLMCall"
    PLATFORM_TOOL = "PlatformTool"
    CONDITION = "ConditionBranch"
    RELEVANCE_GRADE = "RelevanceGrade"
    STATIC_RESPONSE = "StaticResponse"
    PARALLEL_JOIN = "ParallelJoin"
    IMAGE_GENERATE = "ImageGenerate"
    VIDEO_GENERATE = "VideoGenerate"
    SUB_FLOW = "SubFlow"
    LOOP = "LoopNode"
    COMPLIANCE_CHECK = "ComplianceCheck"
    OCR_EXTRACT = "OcrExtract"
    AUDIO_TRANSCRIBE = "AudioTranscribe"


def parse_canvas_node_type(type_str: str) -> CanvasNodeType:
    """将 graph JSON 中的 type 字符串解析为枚举；未知类型抛 ``ValueError``。"""
    return CanvasNodeType(type_str)


MAX_SUBFLOW_DEPTH = 3
MAX_LOOP_ITERATIONS = 100

CONDITIONAL_NODE_TYPES = frozenset({CanvasNodeType.CONDITION, CanvasNodeType.RELEVANCE_GRADE})
TEXT_OUTPUT_NODE_TYPES = frozenset({CanvasNodeType.TEXT_OUTPUT})
CANVAS_NODE_TYPES = frozenset(CanvasNodeType)
