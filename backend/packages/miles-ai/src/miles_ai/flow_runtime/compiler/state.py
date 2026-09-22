"""LangGraph 状态通道、reducer、入边聚合与条件路由。"""

import operator
from typing import Annotated, Any, TypedDict

from miles_ai.flow_runtime.compiler.report import resolve_node_type
from miles_ai.flow_runtime.constants import TEXT_OUTPUT_NODE_TYPES
from miles_ai.flow_runtime.graph_analysis import GRADE_BRANCH_HANDLES
from miles_ai.flow_runtime.types import FlowGraph
from miles_ai.integrations.langgraph.constants import RELEVANCE_NONE


def merge_outputs(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """LangGraph State 中 outputs 字段的 reducer。"""
    return {**left, **right}


class CanvasGraphState(TypedDict, total=False):
    """LangGraph 画布状态通道定义。

    ``total=False``：初始 state 与节点返回值都是局部更新，缺键即缺省。
    但**凡需跨节点传递的键必须在此声明**——LangGraph 只按本 TypedDict 注解建立通道，
    未声明的键在 ``ainvoke`` 时会被**静默丢弃**（不报错，读取端得 ``None``）。
    新增 ``RunContext`` 透传字段时需同步登记，`tests/miles_ai/integrations/langgraph/test_canvas_state_contract.py`
    会锁死「初始 state / 节点读取键 ⊆ 本声明」这一不变式。
    """

    tenant_id: str
    inputs: dict[str, Any]
    kb_ids: list[str]
    model_config_id: str | None
    system_prompt: str | None
    user_id: str | None
    permissions: list[str]
    is_superuser: bool
    agent_id: str | None
    agent_config: dict[str, Any]
    current_flow_id: str | None
    subflow_depth: int
    # 调试/对话注入的附图 [{attachment_id, detail}]，供 LLMCall vision 与媒体节点
    media: list[dict[str, Any]]
    # L1 注入的画布 LLM 解析回调与用量 sink 工厂（随 ctx 透传，编译图单次内存执行）
    resolve_model: Any
    usage_sink_factory: Any
    # L1 注入的 KB 检索绑定载体（随 ctx 透传，KnowledgeSearch 节点装配）
    kb_retrieval: Any
    # L1 注入的生图/生视频模型解析回调（随 ctx 透传，ImageGenerate/VideoGenerate 同步分支）
    resolve_generative_image: Any
    resolve_generative_video: Any
    # L1 注入的生图/生视频异步 job 提交回调（随 ctx 透传，ImageGenerate/VideoGenerate 异步分支）
    submit_generative_image: Any
    submit_generative_video: Any
    invoke_platform_tool: Any
    resolve_prompt_template: Any
    # L1 注入的租户敏感词表加载回调（随 ctx 透传，ComplianceCheck 节点装配）
    load_scan_words: Any
    # L1 注入的子流程图加载回调（随 ctx 透传，SubFlow/LoopNode 节点装配）
    load_subflow_graph: Any
    # L1 注入的附件读取器（随 ctx 透传，OcrExtract/AudioTranscribe 装配）
    media_reader: Any
    # L1 注入的同步生成编排回调（随 ctx 透传）
    generate_image_sync: Any
    generate_video_sync: Any
    outputs: Annotated[dict[str, Any], merge_outputs]
    steps: Annotated[list[dict[str, Any]], operator.add]
    answer: Any


def gather_node_inputs(
    node_id: str,
    incoming: dict[str, list[tuple[str, str, str]]],
    outputs: dict[str, Any],
) -> dict[str, Any]:
    """
    按入边 ``targetHandle`` 聚合上游 ``outputs[node_id]``。

    同时设置 ``input`` 为首个入边值；``rag_flow.json`` 典型：search→prompt 的 handle 为 ``hits``。
    媒体节点可经 ``media`` handle 接收上游附件列表。
    """
    node_inputs: dict[str, Any] = {}
    for src, _sh, th in incoming.get(node_id, []):
        if src not in outputs:
            continue
        raw = outputs[src]
        if isinstance(raw, dict) and "output" in raw:
            val = raw["output"]
        else:
            val = raw
        node_inputs[th] = val
        node_inputs.setdefault("input", val)
        if th == "query":
            node_inputs["query"] = val
        if th == "hits" and val is not None:
            node_inputs["hits"] = val
        if isinstance(raw, dict) and raw.get("hits") is not None:
            node_inputs.setdefault("hits", raw["hits"])
        if th in ("true", "false") and isinstance(raw, dict):
            node_inputs[th] = raw
        if th in GRADE_BRANCH_HANDLES and isinstance(raw, dict):
            node_inputs[th] = raw
        if th == "media" and val is not None:
            node_inputs.setdefault("media", val)
    return node_inputs


def resolve_final_output(fg: FlowGraph, outputs: dict[str, Any]) -> Any:
    """优先 TextOutput 节点值，否则取最后节点输出。"""
    for node in fg.nodes:
        ntype = resolve_node_type(node)
        if ntype in TEXT_OUTPUT_NODE_TYPES:
            val = outputs.get(node["id"])
            if isinstance(val, dict) and "output" in val:
                return val["output"]
            if val is not None:
                return val
    if outputs:
        last = list(outputs.values())[-1]
        if isinstance(last, dict) and "output" in last:
            return last["output"]
        return last
    return None


def make_relevance_grade_router(grade_node_id: str):
    """RelevanceGrade 路由：读取 ``relevance`` 字段（good/poor/none）。"""

    def router(state: dict[str, Any]) -> str:
        raw = (state.get("outputs") or {}).get(grade_node_id, {})
        if isinstance(raw, dict):
            rel = str(raw.get("relevance", RELEVANCE_NONE)).strip().lower()
            if rel in GRADE_BRANCH_HANDLES:
                return rel
        return RELEVANCE_NONE

    return router
