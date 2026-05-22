"""检索相关性 LLM 评分。"""

from __future__ import annotations

import json
import re
from typing import Any

from app.integrations.langchain.chat_models import ainvoke_chat
from app.integrations.langchain.rag import format_hits_context
from app.integrations.langgraph.constants import RELEVANCE_GOOD, RELEVANCE_NONE, RELEVANCE_POOR
from app.models.model import ModelConfig

_GRADE_JSON_RE = re.compile(
    r'\{[^{}]*"relevance"\s*:\s*"(good|poor|none)"[^{}]*\}',
    re.IGNORECASE,
)


def _score_grade(hits: list[dict[str, Any]], threshold: float) -> tuple[str, float]:
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


