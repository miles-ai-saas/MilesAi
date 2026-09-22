"""``run_tool_calling_chat`` 主循环的特征化测试。

目的不是验证新功能，而是**在拆分重构前锁定既有行为**：确认续接、需确认、
工具不存在、模拟调用自救助、生成工具去重、轮次耗尽等分支的响应形态不被改变。

用最小替身（``_Tool`` / ``_Executor``）替代 L1 注入面，并 monkeypatch
``_litellm_with_tools`` 以离线驱动多轮对话。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_core.models.agent.chat_io import ChatRequest
from miles_integrations.langchain.tool_agent import loop as loop_mod
from miles_integrations.langchain.tool_agent.tool_contract import ToolConfirmationSignal

# --- 替身 -------------------------------------------------------------------


class _Tool:
    """最小工具替身：满足 ``_tools_to_openai_schema`` 的 name/description/args_schema。"""

    def __init__(self, name: str) -> None:
        self.name = name
        self.description = name
        self.args_schema = None


class _ToolCall:
    def __init__(self, name: str, arguments: str = "{}", call_id: str = "call-1") -> None:
        self.id = call_id
        self.function = SimpleNamespace(name=name, arguments=arguments)


class _Message:
    def __init__(self, content: str = "", tool_calls=None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _Resp:
    def __init__(self, message: _Message) -> None:
        self.choices = [SimpleNamespace(message=message)]


class _Executor:
    """可编程执行器：meta/invoke 行为由构造参数决定，并记录调用轨迹。"""

    def __init__(self, *, meta=None, invoke=None) -> None:
        self._meta = meta or (lambda slug: {"slug": slug, "name": slug, "require_confirmation": False})
        self._invoke = invoke
        self.invoked: list[tuple[str, dict, bool]] = []

    async def meta(self, slug, *, tool_id=None):  # noqa: ANN001
        result = self._meta(slug)
        if isinstance(result, BaseException):
            raise result
        return result

    async def invoke(self, slug, params, *, confirmed=False, tool_id=None):  # noqa: ANN001
        self.invoked.append((slug, params, confirmed))
        if self._invoke is None:
            return {"message": f"{slug} 已执行"}
        return self._invoke(slug, params, confirmed)


def _agent(**overrides):
    config = {"enable_tool_calling": True, "tool_slugs": ["calculator"], "max_tool_iterations": 3}
    config.update(overrides)
    return SimpleNamespace(model_config=object(), config=config)


def _model():
    return SimpleNamespace(model_type="chat")


def _patch_litellm(monkeypatch, responses):
    """按顺序返回预设响应，并记录每次调用收到的 messages / tools。"""
    seen: dict = {"calls": [], "tools": None}

    async def fake(model, messages, tools, *, temperature):  # noqa: ANN001
        seen["calls"].append(messages)
        seen["tools"] = tools
        return responses.pop(0)

    monkeypatch.setattr(loop_mod, "_litellm_with_tools", fake)
    return seen


async def _run(body, *, agent=None, executor=None, tools=None, kb_ids=None):
    return await loop_mod.run_tool_calling_chat(
        agent if agent is not None else _agent(),
        body,
        system_prompt="sys",
        model=_model(),
        tool_executor=executor if executor is not None else _Executor(),
        platform_tools=tools if tools is not None else [_Tool("calculator")],
        media_reader=None,
        kb_ids=kb_ids,
    )


# --- 无可用工具 --------------------------------------------------------------


async def test_no_tools_returns_guidance():
    resp = await _run(ChatRequest(query="你好"), tools=[])
    assert "未找到可用工具" in resp.answer
    assert resp.steps == [{"type": "tool_agent", "error": "no_tools"}]


# --- 用户确认后继续执行 -------------------------------------------------------


async def test_confirmed_tool_resume_returns_execution_result():
    executor = _Executor(invoke=lambda slug, params, confirmed: {"message": "计算完成"})
    resp = await _run(
        ChatRequest(query="继续", tool_confirmed=True, pending_tool_slug="calculator", pending_tool_params={"expression": "1+1"}),
        executor=executor,
    )
    assert resp.answer == "计算完成"
    assert executor.invoked == [("calculator", {"expression": "1+1"}, True)]
    assert resp.steps == [{"type": "tool_execute", "slug": "calculator", "status": "success"}]
    assert resp.artifacts == []
    assert resp.generative_jobs == []


async def test_confirmed_tool_resume_surfaces_pending_job():
    executor = _Executor(
        invoke=lambda slug, params, confirmed: {
            "status": "pending",
            "generative_job_id": "job-9",
            "kind": "image",
            "message": "已提交",
        }
    )
    resp = await _run(
        ChatRequest(query="继续", tool_confirmed=True, pending_tool_slug="generate_image", pending_tool_params={"prompt": "猫"}),
        executor=executor,
    )
    assert resp.answer == "已提交"
    assert resp.generative_jobs == [{"id": "job-9", "kind": "image", "status": "pending"}]
    assert [a.status for a in resp.artifacts] == ["pending"]
    assert resp.artifacts[0].job_id == "job-9"


async def test_confirmed_tool_resume_failure_is_reported():
    def boom(slug, params, confirmed):
        raise RuntimeError("kaboom")

    resp = await _run(
        ChatRequest(query="继续", tool_confirmed=True, pending_tool_slug="calculator", pending_tool_params={}),
        executor=_Executor(invoke=boom),
    )
    assert "工具执行失败" in resp.answer
    assert resp.steps[0]["status"] == "error"
    assert resp.steps[0]["slug"] == "calculator"


# --- 需确认 -----------------------------------------------------------------


async def test_require_confirmation_returns_pending_tool(monkeypatch):
    _patch_litellm(monkeypatch, [_Resp(_Message("", tool_calls=[_ToolCall("calculator", '{"expression": "1+1"}')]))])

    def invoke(slug, params, confirmed):
        if not confirmed:
            raise ToolConfirmationSignal(slug, "计算器", "用于四则运算", params)
        return {"message": "ok"}

    resp = await _run(
        ChatRequest(query="算一下"),
        executor=_Executor(
            meta=lambda slug: {"slug": slug, "name": slug, "require_confirmation": True},
            invoke=invoke,
        ),
    )
    assert resp.pending_tool is not None
    assert resp.pending_tool.slug == "calculator"
    assert resp.pending_tool.name == "计算器"
    assert resp.pending_tool.description == "用于四则运算"
    assert "需要您确认" in resp.answer
    assert {"type": "tool_confirmation_required", "slug": "calculator"} in resp.steps


# --- 工具不存在 --------------------------------------------------------------


async def test_unknown_tool_returns_config_hint(monkeypatch):
    _patch_litellm(monkeypatch, [_Resp(_Message("", tool_calls=[_ToolCall("ghost", "{}")]))])
    executor = _Executor(meta=lambda slug: BadRequestError("工具不存在"))
    resp = await _run(ChatRequest(query="试一下"), executor=executor)
    assert "ghost" in resp.answer
    assert "tool_slugs" in resp.answer
    assert executor.invoked == []


# --- 轮次耗尽 ---------------------------------------------------------------


async def test_max_iterations_returns_retry_prompt(monkeypatch):
    responses = [_Resp(_Message("", tool_calls=[_ToolCall("calculator", '{"expression": "1+1"}')])) for _ in range(3)]
    _patch_litellm(monkeypatch, responses)
    resp = await _run(ChatRequest(query="算一下"))
    assert "最大轮次" in resp.answer
    assert resp.steps[-1] == {"type": "tool_agent", "error": "max_iterations"}


# --- 续接多轮的消息结构 -------------------------------------------------------


async def test_assistant_tool_call_message_shape(monkeypatch):
    """写入 messages 的 assistant 条目须是 OpenAI tool_calls 结构，content 归一为字符串。"""
    seen = _patch_litellm(
        monkeypatch,
        [
            _Resp(_Message(None, tool_calls=[_ToolCall("calculator", '{"expression": "1+1"}', "call-9")])),
            _Resp(_Message("结果是 2", tool_calls=[])),
        ],
    )
    resp = await _run(ChatRequest(query="算一下"))

    assert resp.answer == "结果是 2"
    second = seen["calls"][1]
    assistant = next(m for m in second if m["role"] == "assistant")
    assert assistant["content"] == ""  # None → ""
    assert assistant["tool_calls"] == [
        {
            "id": "call-9",
            "type": "function",
            "function": {"name": "calculator", "arguments": '{"expression": "1+1"}'},
        }
    ]
    tool_msg = next(m for m in second if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "call-9"


# --- 文本模拟工具调用（自救助）-------------------------------------------------


async def test_tool_simulation_text_is_extracted_and_executed(monkeypatch):
    _patch_litellm(monkeypatch, [_Resp(_Message('calculator(expression="1+1")', tool_calls=[]))])
    executor = _Executor(invoke=lambda slug, params, confirmed: {"message": "结果 2"})
    resp = await _run(ChatRequest(query="算一下"), executor=executor)
    assert resp.answer == "结果 2"
    assert executor.invoked == [("calculator", {"expression": "1+1"}, True)]
    assert any(s.get("type") == "tool_simulation_extracted" for s in resp.steps)


async def test_tool_simulation_without_extractable_params_appends_correction(monkeypatch):
    seen = _patch_litellm(
        monkeypatch,
        [
            # 命中「模拟调用」检测（工具名 + 括号），但参数不可解析 → 走纠正提示
            _Resp(_Message("我来计算：calculator(foo)", tool_calls=[])),
            _Resp(_Message("好的，结果是 2", tool_calls=[])),
        ],
    )
    resp = await _run(ChatRequest(query="算一下"), executor=_Executor())
    assert resp.answer == "好的，结果是 2"
    assert any(s.get("type") == "tool_simulation_corrected" for s in resp.steps)
    # 第二次请求应带上「纠正提示」的 user 消息
    second_messages = seen["calls"][1]
    assert any(m["role"] == "user" and "tool_use" in str(m.get("content", "")) for m in second_messages)


async def test_bare_generative_json_is_not_attributed_to_unrelated_tool(monkeypatch):
    """正文里的裸生图参数 JSON 不得被硬塞给「第一个工具」。

    回归：``_extract_tool_params_from_text`` 在没有任何工具的 name 命中 ``image``/``video``
    时，会兜底 ``return tool_names[0]``。于是只会算数的 agent（tools=[calculator]）会拿
    ``{"prompt": ..., "size": ...}`` 去调 calculator，产生一次误导性的失败重试。
    """
    _patch_litellm(
        monkeypatch,
        [
            _Resp(_Message('好的，参数如下：{"prompt": "一只猫", "size": "1024x1024"}', tool_calls=[])),
            _Resp(_Message("我无法生成图片", tool_calls=[])),
        ],
    )
    executor = _Executor()

    resp = await _run(ChatRequest(query="画一只猫"), executor=executor)

    assert executor.invoked == []  # 不得把生图参数塞给 calculator
    assert resp.answer == "我无法生成图片"
    assert [s.get("type") for s in resp.steps].count("tool_simulation_corrected") == 1
    assert not any(s.get("type") == "tool_simulation_extracted" for s in resp.steps)


async def test_tool_simulation_recovery_is_attempted_only_once(monkeypatch):
    """自救助只试一次：第二轮再出现模拟调用文本时按普通回复收束，不无限纠正。"""
    _patch_litellm(
        monkeypatch,
        [
            _Resp(_Message("我来计算：calculator(foo)", tool_calls=[])),
            _Resp(_Message("还是 calculator(foo)", tool_calls=[])),
        ],
    )
    resp = await _run(ChatRequest(query="算一下"))

    assert resp.answer == "还是 calculator(foo)"
    assert [s.get("type") for s in resp.steps].count("tool_simulation_corrected") == 1
    assert resp.steps[-1].get("error") != "max_iterations"


# --- 生成工具重复调用去重 -----------------------------------------------------


async def test_generative_duplicate_calls_are_merged(monkeypatch):
    seen = _patch_litellm(
        monkeypatch,
        [
            _Resp(
                _Message(
                    "",
                    tool_calls=[
                        _ToolCall("generate_image", '{"prompt": "a"}', "c1"),
                        _ToolCall("generate_image", '{"prompt": "a"}', "c2"),
                    ],
                )
            ),
            _Resp(_Message("已生成", tool_calls=[])),
        ],
    )
    executed: list[str] = []

    def invoke(slug, params, confirmed):
        executed.append(slug)
        return {"kind": "image", "status": "success", "attachment_id": str(uuid4()), "message": "done"}

    resp = await _run(
        ChatRequest(query="画只猫"),
        agent=_agent(tool_slugs=["generate_image"]),
        executor=_Executor(invoke=invoke),
        tools=[_Tool("generate_image")],
    )
    assert executed == ["generate_image"]  # 第二次被合并
    assert resp.answer == "已生成"
    # 被合并那次应回一条 tool 消息告知 LLM，避免它继续重复调用
    second_messages = seen["calls"][1]
    assert any(m.get("role") == "tool" and "自动合并" in str(m.get("content", "")) for m in second_messages)


# --- 同步生成结果产出 artifacts -----------------------------------------------


async def test_successful_generative_artifact_is_returned(monkeypatch):
    attachment_id = str(uuid4())
    _patch_litellm(
        monkeypatch,
        [
            _Resp(_Message("", tool_calls=[_ToolCall("generate_image", '{"prompt": "a"}')])),
            _Resp(_Message("完成", tool_calls=[])),
        ],
    )
    executor = _Executor(
        invoke=lambda slug, params, confirmed: {
            "kind": "image",
            "status": "success",
            "attachment_id": attachment_id,
            "mime_type": "image/png",
            "message": "图好了",
        }
    )
    resp = await _run(
        ChatRequest(query="画只猫"),
        agent=_agent(tool_slugs=["generate_image"]),
        executor=executor,
        tools=[_Tool("generate_image")],
    )
    assert resp.answer == "完成"
    assert [a.kind for a in resp.artifacts] == ["image"]
    assert str(resp.artifacts[0].attachment_id) == attachment_id
    assert any(s.get("type") == "tool_call" and s.get("status") == "success" for s in resp.steps)


# --- 绑定 KB 时强制保留 knowledge_search --------------------------------------


async def test_kb_binding_keeps_knowledge_search_tool(monkeypatch):
    seen = _patch_litellm(monkeypatch, [_Resp(_Message("直接回答", tool_calls=[]))])
    executor = _Executor()
    resp = await _run(
        ChatRequest(query="知识库问题"),
        agent=_agent(tool_slugs=["calculator"]),
        executor=executor,
        tools=[_Tool("calculator"), _Tool("knowledge_search")],
        kb_ids=["kb-1"],
    )
    names = {t["function"]["name"] for t in seen["tools"]}
    assert {"calculator", "knowledge_search"} <= names
    assert resp.answer == "直接回答"


@pytest.mark.parametrize("model_type", ["chat", "vision"])
async def test_multimodal_warning_only_for_non_vision_model(model_type, monkeypatch):
    _patch_litellm(monkeypatch, [_Resp(_Message("回答", tool_calls=[]))])
    body = ChatRequest(query="看图", media=[{"attachment_id": uuid4()}])

    media_parts = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}]

    async def fake_resolve(reader, media, *, max_count):  # noqa: ANN001
        return media_parts

    monkeypatch.setattr(loop_mod, "resolve_media_refs", fake_resolve)
    resp = await loop_mod.run_tool_calling_chat(
        _agent(),
        body,
        system_prompt="sys",
        model=SimpleNamespace(model_type=model_type),
        tool_executor=_Executor(),
        platform_tools=[_Tool("calculator")],
        media_reader=object(),
    )
    warned = any(s.get("type") == "multimodal_warning" for s in resp.steps)
    assert warned is (model_type != "vision")
