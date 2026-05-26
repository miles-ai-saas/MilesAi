"""智能体 KB + tool calling 路由（技能包 / 生图生视频）。"""

from uuid import uuid4

from app.models.agent import Agent
from app.tenant.agents.services.agent import should_use_skill_tools_with_kb


def _agent(**config):
    a = Agent()
    a.model_config_id = uuid4()
    a.config = config
    return a


def test_should_use_skill_tools_with_kb():
    assert should_use_skill_tools_with_kb(
        _agent(enable_tool_calling=True, skill_package_id=str(uuid4())),
        ["kb1"],
    )
    assert should_use_skill_tools_with_kb(
        _agent(enable_tool_calling=True, enable_generative_tools=True),
        ["kb1"],
    )
    assert not should_use_skill_tools_with_kb(
        _agent(enable_tool_calling=True),
        ["kb1"],
    )
    assert not should_use_skill_tools_with_kb(
        _agent(enable_generative_tools=True),
        ["kb1"],
    )
    assert not should_use_skill_tools_with_kb(
        _agent(enable_tool_calling=True, skill_package_id=str(uuid4())),
        [],
    )
