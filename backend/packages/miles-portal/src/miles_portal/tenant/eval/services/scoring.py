"""评测打分：规则优先，可选 LLM judge（rubric）。"""

from __future__ import annotations

from typing import Any


def score_with_rules(answer: str, expected: dict[str, Any] | None) -> tuple[float | None, bool | None, dict]:
    """按 expected 规则打分；无匹配规则时返回 (None, None, detail)。"""
    if not expected:
        return None, None, {"method": "none"}

    text = answer or ""
    if "exact" in expected:
        target = str(expected["exact"])
        ok = text.strip() == target.strip()
        return (1.0 if ok else 0.0), ok, {"method": "exact"}

    if "contains" in expected:
        needle = str(expected["contains"])
        ok = needle in text
        return (1.0 if ok else 0.0), ok, {"method": "contains", "needle": needle}

    if "contains_all" in expected:
        needles = [str(x) for x in (expected["contains_all"] or [])]
        missing = [n for n in needles if n not in text]
        ok = not missing
        return (1.0 if ok else 0.0), ok, {"method": "contains_all", "missing": missing}

    return None, None, {"method": "none"}


async def score_with_llm_judge(
    *,
    answer: str,
    query: str,
    rubric: str,
    model,
) -> tuple[float | None, bool | None, dict]:
    """用 LLM 按 rubric 打分；失败时返回 score=None。"""
    from miles_integrations.langchain.chat_models import ainvoke_chat

    prompt = (
        "你是评测裁判。根据评分标准判断助手回答是否合格。\n"
        "只输出 JSON：{\"score\": 0到1的小数, \"passed\": true/false, \"reason\": \"简短说明\"}\n\n"
        f"用户问题：{query}\n"
        f"评分标准：{rubric}\n"
        f"助手回答：{answer}\n"
    )
    try:
        raw = await ainvoke_chat(
            model,
            [{"role": "user", "content": prompt}],
            temperature=0.0,
        )
    except Exception as exc:
        return None, None, {"method": "llm_judge", "error": str(exc)[:500]}

    import json
    import re

    m = re.search(r"\{.*\}", raw or "", flags=re.DOTALL)
    if not m:
        return None, None, {"method": "llm_judge", "error": "invalid_json", "raw": (raw or "")[:300]}
    try:
        data = json.loads(m.group(0))
        score = float(data.get("score"))
        score = max(0.0, min(1.0, score))
        passed = bool(data.get("passed", score >= 0.5))
        return score, passed, {"method": "llm_judge", "reason": str(data.get("reason", ""))[:500]}
    except Exception as exc:
        return None, None, {"method": "llm_judge", "error": str(exc)[:300], "raw": (raw or "")[:300]}


async def score_case(
    *,
    answer: str,
    query: str,
    expected: dict[str, Any] | None,
    scoring_mode: str,
    model=None,
) -> tuple[float | None, bool | None, dict]:
    """按 run.scoring_mode 打分。"""
    mode = (scoring_mode or "auto").strip().lower()
    if mode in ("auto", "rules"):
        score, passed, detail = score_with_rules(answer, expected)
        if score is not None or mode == "rules":
            return score, passed, detail
        # auto 且无规则：尝试 rubric
        if expected and expected.get("rubric") and model is not None:
            return await score_with_llm_judge(
                answer=answer,
                query=query,
                rubric=str(expected["rubric"]),
                model=model,
            )
        return None, None, detail

    if mode == "llm_judge":
        rubric = str((expected or {}).get("rubric") or "回答应正确、完整、与问题相关。")
        if model is None:
            return None, None, {"method": "llm_judge", "error": "no_model"}
        return await score_with_llm_judge(answer=answer, query=query, rubric=rubric, model=model)

    return None, None, {"method": "unknown_mode", "scoring_mode": mode}
