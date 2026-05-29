"""LLM 评分解析。"""

from app.integrations.langgraph.constants import RELEVANCE_POOR
from app.integrations.langgraph.grading import parse_llm_grade_response


def test_parse_partial_json():
    rel, reason = parse_llm_grade_response('说明如下 {"relevance":"poor","reason":"偏题"} 结束')
    assert rel == RELEVANCE_POOR
    assert "偏题" in reason
