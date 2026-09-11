"""智能体 KB + tool calling 路由（RAG 与 function calling 共存）。"""

from uuid import uuid4

from miles_core.models.agent import Agent
from miles_portal.tenant.agents.services.agent import should_use_tools_with_kb


def _agent(**config):
    a = Agent()
    a.model_config_id = uuid4()
    a.config = config
    return a


def test_should_use_tools_with_kb():
    # 技能包
    assert should_use_tools_with_kb(
        _agent(enable_tool_calling=True, skill_package_id=str(uuid4())),
        ["kb1"],
    )
    # 生图生视频
    assert should_use_tools_with_kb(
        _agent(enable_tool_calling=True, enable_generative_tools=True),
        ["kb1"],
    )
    # 仅 enable_tool_calling：绑定 KB 时也走 tool_agent（knowledge_search 作为工具）
    assert should_use_tools_with_kb(_agent(enable_tool_calling=True), ["kb1"])
    # 仅生图工具
    assert should_use_tools_with_kb(_agent(enable_generative_tools=True), ["kb1"])


def test_should_not_use_tools_without_kb_model_or_flag():
    assert not should_use_tools_with_kb(
        _agent(enable_tool_calling=True, skill_package_id=str(uuid4())),
        [],
    )
    assert not should_use_tools_with_kb(_agent(), ["kb1"])

    no_model = Agent()
    no_model.model_config_id = None
    no_model.config = {"enable_tool_calling": True}
    assert not should_use_tools_with_kb(no_model, ["kb1"])
