"""DeepAgents 编排（平台规划降级路径）。"""

from uuid import uuid4

from miles_core.models.agent import Agent
from miles_integrations.deepagents.orchestrator import _parse_plan, _should_use_deepagents


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
    from miles_core.models.agent import AgentSubAgentBinding
    from miles_integrations.deepagents.subagent_graphs import _slug_for_binding

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


def test_general_purpose_guard_name(monkeypatch):
    """guard 名字为 general-purpose（deepagents 为 optional 依赖，用替身验证）。"""
    from miles_core.models.agent import AgentSubAgentBinding
    from miles_integrations.deepagents import subagent_graphs

    class FakeCompiledSubAgent:
        """极简替身：记录构造参数，兼容属性与下标访问。"""

        def __init__(self, **kwargs):
            self._data = dict(kwargs)
            self.name = kwargs.get("name")

        def __getitem__(self, key):
            return self._data[key]

    # 未安装 agent-stack extras 时模块级 CompiledSubAgent 为 None，此处注入替身
    monkeypatch.setattr(subagent_graphs, "CompiledSubAgent", FakeCompiledSubAgent)

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
    guard = subagent_graphs._build_general_purpose_guard([b])
    assert guard is not None
    assert guard["name"] == "general-purpose"
