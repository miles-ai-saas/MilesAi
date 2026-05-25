"""
流程控制节点（由 LangGraph 编译器接条件边 / 并行层）。

ConditionBranch
---------------
上游常接 **KnowledgeSearch** 的 ``hits`` 列表，``mode`` 支持：
- ``has_hits``：是否有检索命中
- ``score_above``：top score ≥ threshold（默认 0.35，与 RAG 图阈值一致）
- ``text_contains`` / ``not_empty``：对文本输入做简单判断

返回 ``branch`` 为 ``"true"`` / ``"false"``，compiler 映射为条件边 handle。

ParallelJoin
------------
合并并行扇出分支；``merge_strategy``：``dict`` | ``concat_text`` | ``first``。
"""

from __future__ import annotations

from typing import Any

from app.flow_runtime.types import RunContext


def _norm_branch(value: str) -> str:
    """将条件边返回值规范为 true/false 字符串。"""
    v = (value or "").strip().lower()
    if v in ("true", "yes", "1", "branch_true"):
        return "true"
    return "false"


async def condition_branch(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """根据上游结果选择 true/false 分支（由 LangGraph 条件边路由）。"""
    mode = str(node_data.get("mode") or "has_hits")
    threshold = float(node_data.get("threshold", 0.35))
    keyword = str(node_data.get("keyword") or "")

    hits = inputs.get("hits")
    if hits is None and isinstance(inputs.get("input"), list):
        hits = inputs.get("input")
    value = inputs.get("value")
    if value is None:
        value = inputs.get("input")

    branch = "false"
    detail: Any = None

    if mode == "has_hits":
        hit_list = hits if isinstance(hits, list) else []
        branch = "true" if len(hit_list) > 0 else "false"
        detail = len(hit_list)
    elif mode == "score_above":
        hit_list = hits if isinstance(hits, list) else []
        if hit_list:
            top = max(h.get("score", 0) for h in hit_list if isinstance(h, dict))
            branch = "true" if top >= threshold else "false"
            detail = top
        else:
            detail = 0.0
    elif mode == "text_contains":
        text = str(value or "")
        branch = "true" if keyword and keyword in text else "false"
        detail = keyword
    elif mode == "not_empty":
        text = str(value or "").strip()
        branch = "true" if text else "false"
        detail = bool(text)
    else:
        branch = "true" if value else "false"
        detail = mode

    return {
        "branch": branch,
        "mode": mode,
        "detail": detail,
        "preview": str(value)[:120] if value is not None else None,
    }


async def parallel_join(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """合并并行分支输出，供下游单节点消费。"""
    strategy = str(node_data.get("merge_strategy") or "dict")
    branches: dict[str, Any] = {}
    for key, val in inputs.items():
        if key in ("input",):
            continue
        branches[key] = val

    if strategy == "concat_text":
        parts = [str(v) for v in branches.values() if v is not None]
        merged = "\n\n".join(parts)
        output = merged
    elif strategy == "first":
        merged = next(iter(branches.values()), None)
        output = merged
    else:
        merged = branches
        output = inputs.get("input")
        if output is None and branches:
            output = next(iter(branches.values()))

    return {
        "merged": merged,
        "branches": branches,
        "output": output,
    }
