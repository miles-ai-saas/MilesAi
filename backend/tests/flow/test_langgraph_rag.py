"""LangGraph RAG 路由与开关（不依赖 Weaviate）。"""

from uuid import uuid4


from app.integrations.langgraph.constants import RELEVANCE_GOOD, RELEVANCE_NONE, RELEVANCE_POOR
from app.integrations.langgraph.grading import _score_grade, parse_llm_grade_response
from app.integrations.langgraph.graphs.rag_qa import route_after_grade
from app.integrations.langgraph.runner import build_rag_thread_id, should_use_langgraph_rag
from app.models.agent import Agent
from app.tenant.agents.constants import AgentRuntimeMode


def test_route_none_goes_fallback():
    assert route_after_grade({"relevance": RELEVANCE_NONE}) == "fallback"


def test_route_poor_retries_then_fallback():
    assert route_after_grade({"relevance": RELEVANCE_POOR, "retry_count": 0, "max_retries": 1}) == "retry"
    assert route_after_grade({"relevance": RELEVANCE_POOR, "retry_count": 1, "max_retries": 1}) == "fallback"


def test_route_good_generates():
    assert route_after_grade({"relevance": RELEVANCE_GOOD}) == "generate"


def test_score_grade_threshold():
    rel, score = _score_grade([{"score": 0.5}], 0.35)
    assert rel == RELEVANCE_GOOD
    assert score == 0.5
    rel, _ = _score_grade([{"score": 0.1}], 0.35)
    assert rel == RELEVANCE_POOR
    rel, _ = _score_grade([], 0.35)
    assert rel == RELEVANCE_NONE


def test_parse_llm_grade_response():
    rel, _ = parse_llm_grade_response('{"relevance":"good","reason":"ok"}')
    assert rel == RELEVANCE_GOOD
    rel, _ = parse_llm_grade_response("结论：none，无相关内容")
    assert rel == RELEVANCE_NONE


def test_build_rag_thread_id():
    tid = uuid4()
    aid = uuid4()
    assert build_rag_thread_id(tenant_id=tid, agent_id=aid) == f"{tid}:{aid}:default"
    assert build_rag_thread_id(tenant_id=tid, agent_id=aid, conversation_id="sess-1") == (f"{tid}:{aid}:sess-1")


def test_should_use_langgraph_rag_flags():
    agent = Agent(
        id=uuid4(),
        tenant_id=uuid4(),
        name="t",
        config={},
    )
    assert should_use_langgraph_rag(agent, kb_ids=["kb"]) is True
    agent.config = {"use_langgraph_rag": False}
    assert should_use_langgraph_rag(agent, kb_ids=["kb"]) is False
    agent.config = {"runtime_mode": AgentRuntimeMode.LEGACY.value}
    assert should_use_langgraph_rag(agent, kb_ids=["kb"]) is False
    agent.config = {"runtime_mode": AgentRuntimeMode.AUTONOMOUS.value}
    assert should_use_langgraph_rag(agent, kb_ids=["kb"]) is False
    assert should_use_langgraph_rag(agent, kb_ids=[]) is False
