"""
RAG LangGraph 检索相关性评分（``grade_documents`` 节点）。

策略
----
1. **默认**：``_score_grade`` — 取 hits 最高 ``score`` 与 ``relevance_threshold``（默认 0.35）比较
2. **可选**：``agent.config.use_llm_grade=true`` 时 ``llm_grade_relevance`` 让 LLM 输出 JSON
   ``{"relevance":"good"|"poor"|"none","reason":"..."}``

输出驱动 ``route_after_grade``：good → generate；poor → retry；none → fallback。
"""

from __future__ import annotations

import json
import re
from typing import Any

from miles_ai.rag.generate import format_hits_context
from miles_ai.rag.graph.constants import RELEVANCE_GOOD, RELEVANCE_NONE, RELEVANCE_POOR
from miles_core.models.model import ModelConfig
from miles_integrations.langchain.chat_models import ainvoke_chat

_GRADE_VALUES = "|".join(re.escape(v) for v in (RELEVANCE_GOOD, RELEVANCE_POOR, RELEVANCE_NONE))
_GRADE_JSON_RE = re.compile(
    rf'\{{[^{{}}]*"relevance"\s*:\s*"({_GRADE_VALUES})"[^{{}}]*\}}',
    re.IGNORECASE,
)


def _score_grade(hits: list[dict[str, Any]], threshold: float) -> tuple[str, float]:
    """按 top hit 分数与阈值映射 good/poor/none。"""
    if not hits:
        return RELEVANCE_NONE, 0.0
    top_score = max(h.get("score", 0) for h in hits)
    if top_score >= threshold:
        return RELEVANCE_GOOD, top_score
    return RELEVANCE_POOR, top_score


def parse_llm_grade_response(text: str) -> tuple[str, str]:
    """解析 LLM 返回的 relevance，失败时返回 (empty, reason)。"""
    text = (text or "").strip()
    if not text:
        return "", ""
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            rel = str(data.get("relevance", "")).lower()
            reason = str(data.get("reason", ""))[:500]
            if rel in (RELEVANCE_GOOD, RELEVANCE_POOR, RELEVANCE_NONE):
                return rel, reason
    except json.JSONDecodeError:
        # 静默可接受：模型输出不保证是 JSON；解析失败由调用方走默认降级。
        pass
    match = _GRADE_JSON_RE.search(text)
    if match:
        rel = match.group(1).lower()
        return rel, text[:500]
    lowered = text.lower()
    if "none" in lowered or "无相关" in text or "不相关" in text:
        return RELEVANCE_NONE, text[:500]
    if "poor" in lowered or "不足" in text or "偏低" in text:
        return RELEVANCE_POOR, text[:500]
    if "good" in lowered or "相关" in text:
        return RELEVANCE_GOOD, text[:500]
    return "", text[:500]


async def evaluate_relevance(
    hits: list[dict[str, Any]],
    *,
    query: str,
    threshold: float = 0.35,
    use_llm_grade: bool = False,
    model: ModelConfig | None = None,
) -> dict[str, Any]:
    """
    画布 ``RelevanceGrade`` 与 ``rag_qa.grade_documents`` 共用的评分逻辑。

    返回 ``relevance``（good/poor/none）、``top_score``、``reason``、``grade_method``。
    """
    relevance, top_score = _score_grade(hits, threshold)
    reason = ""
    grade_method = "score"

    if use_llm_grade and hits and model is not None:
        try:
            llm_rel, reason = await llm_grade_relevance(
                model,
                query=query,
                hits=hits,
            )
            if llm_rel:
                relevance = llm_rel
                grade_method = "llm"
        except Exception as exc:
            grade_method = "score_fallback"
            reason = str(exc)[:200]

    return {
        "relevance": relevance,
        "top_score": top_score,
        "reason": reason[:300] if reason else None,
        "grade_method": grade_method,
        "hits": hits,
    }


async def llm_grade_relevance(
    model: ModelConfig,
    *,
    query: str,
    hits: list[dict[str, Any]],
    max_snippets: int = 3,
) -> tuple[str, str]:
    """用 LLM 判断检索结果与问题的相关性。"""
    snippets = format_hits_context(hits[:max_snippets])
    if len(snippets) > 2400:
        snippets = snippets[:2400] + "\n…（已截断）"
    prompt = (
        "你是检索质量评估器。根据用户问题与检索片段，判断资料是否足以回答问题。\n"
        "只输出一行 JSON，不要其它文字："
        '{"relevance":"good"|"poor"|"none","reason":"简短理由"}\n'
        "- good: 片段与问题高度相关，可支撑回答\n"
        "- poor: 有部分相关但不足或偏题\n"
        "- none: 完全不相关或无有效内容\n\n"
        f"用户问题：{query}\n\n检索片段：\n{snippets or '（无）'}"
    )
    raw = await ainvoke_chat(model, [{"role": "user", "content": prompt}], temperature=0)
    rel, reason = parse_llm_grade_response(raw)
    return rel or RELEVANCE_POOR, reason or raw[:300]
