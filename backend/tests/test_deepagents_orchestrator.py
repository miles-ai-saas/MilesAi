"""DeepAgents 编排（平台规划降级路径）。"""

from uuid import uuid4

from app.ai_stack.deepagents.orchestrator import _parse_plan, _should_use_deepagents
from app.models.agent import Agent


def test_parse_plan_json():
    raw = '{"steps":[{"sub_agent_id":"11111111-1111-1111-1111-111111111111","task":"检索政策"}]}'
    plan = _parse_plan(raw)
    assert len(plan) == 1
    assert plan[0]["task"] == "检索政策"


def test_should_use_deepagents_without_package():
    agent = Agent(
        id=uuid4(),
        tenant_id=uuid4(),
        name="p",
        config={"planner": "deepagents", "force_platform_planner": True},
    )
    assert _should_use_deepagents(agent) is False


def test_slug_for_binding():
    from app.ai_stack.deepagents.subagent_graphs import _slug_for_binding
    from app.models.agent import AgentSubAgentBinding

    class Child:
        id = uuid4()
        name = "检索助手"
        description = "d"

    b = AgentSubAgentBinding(
        parent_agent_id=uuid4(),
        child_agent_id=uuid4(),
        role_hint="retrieval",
        sort_order=0,
    )
    b.child_agent = Child()  # type: ignore[attr-defined]
    slug = _slug_for_binding(b)
    assert slug.startswith("retrieval_")


def test_general_purpose_guard_name():
    from app.ai_stack.deepagents.subagent_graphs import _build_general_purpose_guard
    from app.models.agent import AgentSubAgentBinding

    class Child:
        id = uuid4()
        name = "子"
        description = ""

    b = AgentSubAgentBinding(
        parent_agent_id=uuid4(),
        child_agent_id=uuid4(),
        role_hint="summary",
        sort_order=0,
    )
    b.child_agent = Child()  # type: ignore[attr-defined]
    guard = _build_general_purpose_guard([b])
    assert guard is not None
    assert guard["name"] == "general-purpose"
