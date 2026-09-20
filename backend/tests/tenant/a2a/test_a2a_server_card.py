"""A2A Server（对外暴露）：Card 构造、发布门槛、JSON-RPC 信封与文本解析。

与 ``test_a2a_card_client.py``（拉取远端 Card）方向相反，本文件覆盖本平台产 Card、
收 ``message/send`` 的一侧。纯函数与服务分别验证：
1. ``miles_portal.tenant.a2a.server`` 的 Card / 信封 / parts 解析（无 DB）；
2. ``a2a.services.server`` 的发布门槛与默认发布智能体解析（fake DB）。
"""

from __future__ import annotations

import asyncio
import inspect
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_common.schemas.chat_io import ChatResponse
from miles_core.models.agent import Agent, AgentStatus, AgentType
from miles_portal.tenant.a2a import server as server_mod
from miles_portal.tenant.a2a.server import (
    A2A_PUBLISH_FLAG,
    a2a_task_artifact_path,
    artifact_ids_from_job_result,
    build_a2a_agent_message,
    build_a2a_artifacts,
    build_a2a_status_update,
    build_a2a_task,
    build_agent_card,
    extract_message_context_id,
    extract_message_text,
    is_active_generative_status,
    is_publish_enabled,
    jsonrpc_error,
    jsonrpc_result,
    to_a2a_task_state,
)
from miles_portal.tenant.a2a.services import server as server_svc

AGENT_ID = uuid4()
BASE = "https://miles.example.com"


# --- 1. 纯函数 ---------------------------------------------------------------


def test_is_publish_enabled_reads_config_flag():
    assert is_publish_enabled({A2A_PUBLISH_FLAG: True}) is True
    assert is_publish_enabled({A2A_PUBLISH_FLAG: "true"}) is False
    assert is_publish_enabled({A2A_PUBLISH_FLAG: False}) is False
    assert is_publish_enabled({}) is False
    assert is_publish_enabled(None) is False


def test_build_agent_card_declares_rpc_interface_and_fallback_skill():
    card = build_agent_card(agent_id=AGENT_ID, name="客服助手", description="解答售后问题", base_url=BASE)

    assert card["name"] == "客服助手"
    assert card["description"] == "解答售后问题"
    rpc_url = f"{BASE}/api/v1/open/a2a/agents/{AGENT_ID}"
    assert card["url"] == rpc_url
    assert card["additionalInterfaces"] == [{"url": rpc_url, "transport": "JSONRPC"}]
    # 未绑定技能包时，智能体自身即一个 skill（Card 不允许 skills 为空数组）
    assert [s["id"] for s in card["skills"]] == [str(AGENT_ID)]
    assert card["skills"][0]["name"] == "客服助手"


def test_build_agent_card_declares_api_key_security_scheme():
    """Card 须声明调用端点的鉴权方式，否则标准 A2A 客户端无从得知要带 ``X-API-Key``。"""
    card = build_agent_card(agent_id=AGENT_ID, name="客服助手", description="D", base_url=BASE)

    assert card["securitySchemes"] == {
        "apiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "该智能体的 API Key，在智能体详情中创建",
        }
    }
    assert card["security"] == [{"apiKey": []}]


def test_declared_security_header_matches_actual_auth_header():
    """Card 声明的头名必须与实际鉴权头一致 —— 二者漂移会让对端带着错误的头调用。

    生产侧共用同一常量，本测试直接比对「Card 声明」与「FastAPI 依赖实际读取的 alias」。
    """
    from miles_portal.tenant.agents.deps_api_auth import require_agent_api_key

    card = build_agent_card(agent_id=AGENT_ID, name="N", description=None, base_url=BASE)
    declared = card["securitySchemes"]["apiKey"]["name"]

    param = inspect.signature(require_agent_api_key).parameters["x_api_key"]
    assert declared == param.default.alias


def test_build_agent_card_base_url_trailing_slash_is_normalized():
    card = build_agent_card(agent_id=AGENT_ID, name="N", description=None, base_url=f"{BASE}/")
    assert card["url"] == f"{BASE}/api/v1/open/a2a/agents/{AGENT_ID}"
    assert card["description"] == ""


def test_build_agent_card_uses_bound_skill_packages_when_present():
    skills = [{"id": "skill:faq", "name": "FAQ", "description": "常见问题", "tags": ["售后"]}]
    card = build_agent_card(agent_id=AGENT_ID, name="N", description="D", base_url=BASE, skills=skills)
    assert card["skills"] == skills


def test_extract_message_text_joins_text_parts():
    params = {
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": "你好"}, {"type": "text", "text": "在吗"}],
        }
    }
    assert extract_message_text(params) == "你好\n在吗"


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"message": {}},
        {"message": {"parts": []}},
        {"message": {"parts": [{"type": "file", "file": {}}]}},
        {"message": {"parts": [{"type": "text", "text": "   "}]}},
    ],
)
def test_extract_message_text_rejects_payload_without_text(params):
    """缺少文本属调用方参数错误；静默返回空串会让本平台空转一轮对话。"""
    with pytest.raises(BadRequestError):
        extract_message_text(params)


def test_extract_message_context_id_reads_message_level_field():
    """A2A 的 ``contextId`` 挂在 Message 顶层，用于把多轮串成同一上下文。"""
    params = {"message": {"parts": [{"type": "text", "text": "hi"}], "contextId": "ctx-1"}}
    assert extract_message_context_id(params) == "ctx-1"


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"message": {}},
        {"message": {"parts": [], "contextId": "   "}},
        {"message": {"parts": [], "contextId": 123}},
    ],
)
def test_extract_message_context_id_absent_or_invalid_is_none(params):
    """未提供或非法类型一律视为「无上下文」；不猜测、不报错（首轮调用本就没有）。"""
    assert extract_message_context_id(params) is None


def test_extract_message_context_id_rejects_overlong():
    """超长 contextId 会被下游客话契约拒绝（→ 500）；在入口就判为参数错误更可诊断。"""
    with pytest.raises(BadRequestError):
        extract_message_context_id({"message": {"parts": [], "contextId": "c" * 200}})


def test_to_a2a_task_state_maps_platform_status():
    """平台生成任务状态 → A2A ``TaskState``。"""
    assert to_a2a_task_state("pending") == "submitted"
    assert to_a2a_task_state("running") == "working"
    assert to_a2a_task_state("success") == "completed"
    assert to_a2a_task_state("failed") == "failed"
    assert to_a2a_task_state("cancelled") == "canceled"


def test_to_a2a_task_state_unknown_is_not_guessed():
    """未知状态回 A2A 保留值 ``unknown``；猜成 ``completed`` 会让对端以为产物已就绪。"""
    assert to_a2a_task_state("something-new") == "unknown"


@pytest.mark.parametrize(
    ("status", "expected"),
    [("pending", True), ("running", True), ("success", False), ("failed", False), ("cancelled", False)],
)
def test_is_active_generative_status(status, expected):
    """只有非终态任务才值得让对端轮询。"""
    assert is_active_generative_status(status) is expected


def test_unknown_generative_status_counts_as_active():
    """未知状态不当作已结束：与 ``to_a2a_task_state`` 回 ``unknown``（而非 ``completed``）
    同一原则 —— 宁可让对端多轮询一次，也不谎称产物已就绪。"""
    assert is_active_generative_status("some-new-state") is True


def test_build_a2a_task_shape():
    task = build_a2a_task(task_id="j1", context_id="c1", state="working", timestamp="2026-09-18T00:00:00+00:00")

    assert task["kind"] == "task"
    assert task["id"] == "j1"
    assert task["contextId"] == "c1"
    assert task["status"] == {"state": "working", "timestamp": "2026-09-18T00:00:00+00:00"}


def test_build_a2a_task_omits_absent_context_id():
    """contextId 是可选字段：解析不到时省略，不塞空串冒充。"""
    task = build_a2a_task(task_id="j1", context_id=None, state="completed", timestamp="t")
    assert "contextId" not in task


def test_a2a_task_artifact_path_shape():
    assert a2a_task_artifact_path("a1", "t1", "att1") == "/api/v1/open/a2a/agents/a1/tasks/t1/artifacts/att1"


def test_artifact_ids_from_job_result_reads_image_and_video():
    """生图是多产物（``attachment_ids``），生视频单个（``attachment_id``）。"""
    assert artifact_ids_from_job_result({"kind": "image", "attachment_ids": ["a", "b"]}) == ["a", "b"]
    assert artifact_ids_from_job_result({"kind": "video", "attachment_id": "v"}) == ["v"]


@pytest.mark.parametrize("result", [None, {}, {"attachment_ids": []}, {"attachment_ids": None}])
def test_artifact_ids_from_job_result_empty_when_no_artifact(result):
    assert artifact_ids_from_job_result(result) == []


def test_artifact_ids_from_job_result_dedupes_and_drops_blanks():
    """空串/None 不是附件 ID；重复 ID 不应产出两个一样的 artifact。"""
    assert artifact_ids_from_job_result({"attachment_ids": ["a", "a", "", None, "b"]}) == ["a", "b"]


def test_build_a2a_artifacts_points_at_authenticated_download_endpoint():
    """产物 URI 指向本平台的开放下载端点（**需 X-API-Key**），非对象存储签名 URL。"""
    artifacts = build_a2a_artifacts(
        job_result={"kind": "image", "attachment_ids": ["att-1"], "mime_type": "image/png"},
        agent_id=AGENT_ID,
        task_id="task-1",
        base_url=BASE,
    )

    assert len(artifacts) == 1
    assert artifacts[0]["artifactId"] == "att-1"
    part = artifacts[0]["parts"][0]
    assert part["kind"] == "file"
    assert part["file"]["uri"] == f"{BASE}/api/v1/open/a2a/agents/{AGENT_ID}/tasks/task-1/artifacts/att-1"
    assert part["file"]["mimeType"] == "image/png"


def test_build_a2a_artifacts_empty_without_result():
    assert build_a2a_artifacts(job_result=None, agent_id=AGENT_ID, task_id="t", base_url=BASE) == []


def test_build_agent_card_declares_streaming_and_v03():
    """声明必须与实现同版：方法名/payload 全是 0.3，Card 就不能标 1.0。"""
    card = build_agent_card(agent_id=AGENT_ID, name="客服助手", description="D", base_url=BASE)

    assert card["protocolVersion"] == "0.3"
    assert card["preferredTransport"] == "JSONRPC"
    assert card["capabilities"]["streaming"] is True


def test_build_agent_card_uses_v03_interface_field_names():
    """声明 0.3，接口数组就必须是 0.3 的 ``additionalInterfaces`` / ``transport``。

    ``supportedInterfaces`` / ``protocolBinding`` 是 v1.0 的字段名：混用会让按声明办事的
    0.3 客户端读到一对它不认识的键，只能退回 ``url`` + ``preferredTransport`` —— 能跑，
    但等于声明白写；而 v1.0 客户端又会把 ``preferredTransport`` 当陌生字段。
    """
    card = build_agent_card(agent_id=AGENT_ID, name="N", description=None, base_url=BASE)

    assert "supportedInterfaces" not in card
    assert all("protocolBinding" not in item for item in card["additionalInterfaces"])
    # 主 url 的接口也须出现在 additionalInterfaces 里（v0.3 §5.6.4 的完整性要求）
    assert {"url": card["url"], "transport": card["preferredTransport"]} in card["additionalInterfaces"]


def test_task_state_rejected_constant_exists():
    """合规拦截要回 A2A ``rejected``（拒绝处理），不借用 ``failed``。"""
    assert server_mod.TASK_STATE_REJECTED == "rejected"


def test_build_a2a_agent_message_shape():
    message = build_a2a_agent_message(text="订单已发货", context_id="ctx-1")

    assert message["kind"] == "message"
    assert message["role"] == "agent"
    assert message["contextId"] == "ctx-1"
    # 0.3 的 Part 判别键是 kind：发 type 会被严格的对端当未知 part 丢掉
    assert message["parts"] == [{"kind": "text", "text": "订单已发货"}]
    assert message["messageId"]
    assert "taskId" not in message


def test_build_a2a_agent_message_carries_task_id_when_given():
    message = build_a2a_agent_message(text="增量", context_id="ctx-1", task_id="t-1")

    assert message["taskId"] == "t-1"


def test_build_a2a_artifacts_part_kind_is_file():
    artifacts = build_a2a_artifacts(
        job_result={"kind": "image", "attachment_ids": ["att-1"], "mime_type": "image/png"},
        agent_id=AGENT_ID,
        task_id=uuid4(),
        base_url=BASE,
    )

    assert artifacts[0]["parts"][0]["kind"] == "file"


def test_build_a2a_status_update_increment_frame():
    """中间帧：state=working、final=False，文本为本片增量，嵌套消息带 taskId/contextId。"""
    frame = build_a2a_status_update(
        task_id="t-1",
        context_id="ctx-1",
        state=server_mod.TASK_STATE_WORKING,
        timestamp="2026-09-18T09:00:00+00:00",
        text="甲",
        final=False,
    )

    assert frame["kind"] == "status-update"
    assert frame["taskId"] == "t-1"
    assert frame["contextId"] == "ctx-1"
    assert frame["final"] is False
    assert frame["status"]["state"] == "working"
    assert frame["status"]["timestamp"] == "2026-09-18T09:00:00+00:00"
    assert frame["status"]["message"]["taskId"] == "t-1"
    assert frame["status"]["message"]["contextId"] == "ctx-1"
    assert frame["status"]["message"]["parts"] == [{"kind": "text", "text": "甲"}]


def test_build_a2a_status_update_final_frame_carries_full_answer():
    frame = build_a2a_status_update(
        task_id="t-1",
        context_id="ctx-1",
        state=server_mod.TASK_STATE_COMPLETED,
        timestamp="2026-09-18T09:00:01+00:00",
        text="甲乙丙",
        final=True,
    )

    assert frame["final"] is True
    assert frame["status"]["state"] == "completed"
    assert frame["status"]["message"]["parts"][0]["text"] == "甲乙丙"
    assert "metadata" not in frame["status"]["message"]


def test_build_a2a_status_update_exposes_job_task_id_in_metadata():
    """本轮产生异步生成任务时，末帧给出真实 job id，对端才能转向 tasks/get 轮询产物。"""
    frame = build_a2a_status_update(
        task_id="t-1",
        context_id="ctx-1",
        state=server_mod.TASK_STATE_WORKING,
        timestamp="2026-09-18T09:00:00+00:00",
        text="正在生成",
        final=True,
        job_task_id="job-1",
    )

    assert frame["status"]["message"]["metadata"] == {"a2aJobTaskId": "job-1"}


def test_build_a2a_status_update_omits_message_without_text():
    """无文本终态不带 message（保留表达能力：终态可以只是状态）。"""
    frame = build_a2a_status_update(
        task_id="t-1",
        context_id="ctx-1",
        state=server_mod.TASK_STATE_FAILED,
        timestamp="2026-09-18T09:00:00+00:00",
        final=True,
    )

    assert "message" not in frame["status"]
    assert "metadata" not in frame


def test_jsonrpc_envelopes():
    assert jsonrpc_result("1", {"ok": True}) == {"jsonrpc": "2.0", "id": "1", "result": {"ok": True}}
    err = jsonrpc_error("1", server_mod.METHOD_NOT_FOUND, "不支持的方法")
    assert err["jsonrpc"] == "2.0"
    assert err["id"] == "1"
    assert err["error"] == {"code": server_mod.METHOD_NOT_FOUND, "message": "不支持的方法"}
    assert "result" not in err


def test_jsonrpc_error_carries_optional_data():
    """超限要在 ``error.data`` 给结构化细节（规范允许），而既有调用形状必须逐字不变。"""
    assert jsonrpc_error(1, -32602, "坏参数") == {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "坏参数"}}

    with_data = jsonrpc_error(1, server_mod.RATE_LIMITED, "请求过于频繁，请稍后再试", data={"kind": "rate_limit", "retryAfterSeconds": 12})
    assert with_data["error"]["data"] == {"kind": "rate_limit", "retryAfterSeconds": 12}


def test_rate_limited_code_is_in_implementation_defined_range():
    """``-32000`` 属规范保留给实现自定义的服务端错误区间（A2A 已占 -32001..-32007）。"""
    assert server_mod.RATE_LIMITED == -32000


# --- 2. 服务：发布门槛 --------------------------------------------------------


def _agent(**overrides):
    agent = Agent()
    agent.id = AGENT_ID
    agent.name = "客服助手"
    agent.description = "D"
    agent.agent_type = AgentType.CUSTOM
    agent.status = AgentStatus.ENABLED
    agent.config = {A2A_PUBLISH_FLAG: True}
    agent.deleted_at = None
    for key, value in overrides.items():
        setattr(agent, key, value)
    return agent


class _Db:
    """最小 fake：``get`` 返回预置智能体，``execute`` 返回预置行。"""

    def __init__(self, agent=None, rows=None):
        self._agent = agent
        self._rows = rows or []
        self.committed = 0
        self.rolled_back = 0

    async def get(self, _model, _id):  # noqa: ANN001
        return self._agent

    async def execute(self, _stmt):  # noqa: ANN001
        return SimpleNamespace(scalars=lambda: iter(self._rows))

    async def commit(self):  # noqa: ANN001
        self.committed += 1

    async def rollback(self):  # noqa: ANN001
        self.rolled_back += 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("agent_type", "status", "flag", "deleted"),
    [
        (AgentType.A2A, AgentStatus.ENABLED, True, False),  # 互联宿主是调用方，不对外
        (AgentType.CUSTOM, AgentStatus.DISABLED, True, False),
        (AgentType.CUSTOM, AgentStatus.ENABLED, False, False),
        (AgentType.CUSTOM, AgentStatus.ENABLED, True, True),  # 已软删
    ],
)
async def test_load_published_agent_rejects_unpublished(monkeypatch, agent_type, status, flag, deleted):  # noqa: ANN001
    monkeypatch.setattr(server_svc, "is_marked_deleted", lambda _row: deleted)
    agent = _agent(agent_type=agent_type, status=status, config={A2A_PUBLISH_FLAG: flag})
    with pytest.raises(NotFoundError):
        await server_svc.load_published_agent(_Db(agent=agent), AGENT_ID)


@pytest.mark.asyncio
async def test_load_published_agent_returns_enabled_custom_with_flag(monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(server_svc, "is_marked_deleted", lambda _row: False)
    agent = _agent()
    assert await server_svc.load_published_agent(_Db(agent=agent), AGENT_ID) is agent


@pytest.mark.asyncio
async def test_build_public_agent_card_maps_bound_skills(monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(server_svc, "is_marked_deleted", lambda _row: False)
    monkeypatch.setattr(
        server_svc,
        "_bound_skill_entries",
        _async_ret([{"id": "skill:faq", "name": "FAQ", "description": None, "tags": []}]),
    )
    card = await server_svc.build_public_agent_card(_Db(agent=_agent()), _agent(), base_url=BASE)
    assert [s["id"] for s in card["skills"]] == ["skill:faq"]


@pytest.mark.asyncio
async def test_build_agent_card_by_id_gates_on_publish(monkeypatch):  # noqa: ANN001
    """API 声明层唯一入口：未发布不返回 Card。"""
    monkeypatch.setattr(server_svc, "is_marked_deleted", lambda _row: False)
    monkeypatch.setattr(server_svc, "_bound_skill_entries", _async_ret([]))

    with pytest.raises(NotFoundError):
        await server_svc.build_agent_card_by_id(_Db(agent=None), AGENT_ID, base_url=BASE)

    card = await server_svc.build_agent_card_by_id(_Db(agent=_agent()), AGENT_ID, base_url=BASE)
    assert card["name"] == "客服助手"


def _async_ret(value):
    async def _inner(*_args, **_kwargs):
        return value

    return _inner


@pytest.mark.asyncio
async def test_resolve_default_published_agent_requires_unambiguous_match():
    """根路径别名只在全平台唯一发布时可用；0 或 >1 都不猜，返回 None。"""
    assert await server_svc.resolve_default_published_agent_id(_Db(rows=[])) is None
    assert await server_svc.resolve_default_published_agent_id(_Db(rows=[AGENT_ID, uuid4()])) is None
    assert await server_svc.resolve_default_published_agent_id(_Db(rows=[AGENT_ID])) == AGENT_ID


# --- 3. JSON-RPC 分发 ---------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_rpc_message_send_returns_agent_message(monkeypatch):  # noqa: ANN001
    async def fake_chat(_db, _ctx, _agent_id, text, conversation_id=None):  # noqa: ANN001
        assert text == "帮我查订单"
        return ChatResponse(answer="订单已发货")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    payload = {
        "jsonrpc": "2.0",
        "id": "abc",
        "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"type": "text", "text": "帮我查订单"}]}},
    }
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert envelope["jsonrpc"] == "2.0"
    assert envelope["id"] == "abc"
    result = envelope["result"]
    assert result["kind"] == "message"
    assert result["role"] == "agent"
    assert result["parts"][0]["text"] == "订单已发货"
    assert result["parts"][0]["kind"] == "text"
    assert result["messageId"]


@pytest.mark.asyncio
async def test_handle_rpc_forwards_context_id_as_conversation(monkeypatch):  # noqa: ANN001
    """``message.contextId`` → ``ChatRequest.conversation_id``，并在响应回显，多轮才成立。"""
    captured: dict = {}

    async def fake_chat(_db, _ctx, _agent_id, text, conversation_id=None):  # noqa: ANN001
        captured["conversation_id"] = conversation_id
        return ChatResponse(answer="继续")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"parts": [{"type": "text", "text": "接着说"}], "contextId": "ctx-42"}},
    }
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert captured["conversation_id"] == "ctx-42"
    assert envelope["result"]["contextId"] == "ctx-42"


@pytest.mark.asyncio
async def test_handle_rpc_assigns_context_id_when_absent(monkeypatch):  # noqa: ANN001
    """首轮未带 contextId 时生成一个，并同样作为 conversation_id 下传。

    必须首轮就用它：否则第一轮 checkpoint 落在别的 thread，对端第二轮带上该
    contextId 时模型并无上一轮记忆，「多轮」名不副实。
    """
    captured: dict = {}

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None):  # noqa: ANN001
        captured["conversation_id"] = conversation_id
        return ChatResponse(answer="初次见面")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"parts": [{"type": "text", "text": "你好"}]}},
    }
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    generated = envelope["result"]["contextId"]
    assert generated
    assert captured["conversation_id"] == generated


@pytest.mark.asyncio
async def test_handle_rpc_maps_overlong_context_id_to_invalid_params():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"parts": [{"type": "text", "text": "hi"}], "contextId": "c" * 200}},
    }
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)
    assert envelope["error"]["code"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_handle_rpc_rejects_non_jsonrpc_payload():
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, ["not", "a", "dict"], base_url=BASE)
    assert envelope["error"]["code"] == server_mod.INVALID_REQUEST
    assert "result" not in envelope


@pytest.mark.asyncio
async def test_handle_rpc_rejects_unsupported_method():
    payload = {"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)
    assert envelope["error"]["code"] == server_mod.METHOD_NOT_FOUND
    assert "message/stream" in envelope["error"]["message"]


@pytest.mark.asyncio
async def test_handle_rpc_maps_missing_text_to_invalid_params():
    payload = {"jsonrpc": "2.0", "id": 1, "method": "message/send", "params": {"message": {"parts": []}}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)
    assert envelope["error"]["code"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_handle_rpc_maps_agent_failure_to_internal_error(monkeypatch):  # noqa: ANN001
    """对话链路异常必须转 JSON-RPC 错误：抛栈会让对端只看到 HTTP 500 无正文。"""

    async def boom(*_args, **_kwargs):
        raise RuntimeError("模型不可用")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", boom)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"parts": [{"type": "text", "text": "hi"}]}},
    }
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)
    assert envelope["error"]["code"] == server_mod.INTERNAL_ERROR
    assert "模型不可用" in envelope["error"]["message"]


# --- 4. Task 生命周期 ---------------------------------------------------------


def _job(status: str, *, params: dict | None = None, job_id=None, result: dict | None = None, agent_id=None):
    return SimpleNamespace(
        id=job_id or uuid4(),
        status=SimpleNamespace(value=status),
        params=params or {},
        result=result,
        source_ref_type="agent" if agent_id else None,
        source_ref_id=agent_id,
    )


@pytest.mark.asyncio
async def test_message_send_returns_task_while_generation_active(monkeypatch):  # noqa: ANN001
    """产生异步生成任务时改回 A2A ``Task``，对端才可轮询/取消；同步回答仍回 ``Message``。"""

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None):  # noqa: ANN001
        return ChatResponse(
            answer="正在生成",
            generative_jobs=[{"id": "job-1", "kind": "video", "status": "pending"}],
        )

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"parts": [{"type": "text", "text": "生成一段视频"}], "contextId": "ctx-9"}},
    }
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    result = envelope["result"]
    assert result["kind"] == "task"
    assert result["id"] == "job-1"
    # 状态照实映射：job 仍 pending（排队中）→ A2A submitted，而非一律 working
    assert result["status"]["state"] == "submitted"
    assert result["contextId"] == "ctx-9"


@pytest.mark.asyncio
async def test_message_send_ignores_terminal_generative_jobs(monkeypatch):  # noqa: ANN001
    """已结束的生成任务无需轮询，仍按 ``Message`` 返回，避免对端多跑一次 tasks/get。"""

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None):  # noqa: ANN001
        return ChatResponse(
            answer="图已生成",
            generative_jobs=[{"id": "job-1", "kind": "image", "status": "success"}],
        )

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"parts": [{"type": "text", "text": "画张图"}]}},
    }
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert envelope["result"]["kind"] == "message"


@pytest.mark.asyncio
async def test_tasks_get_maps_job_state_and_context(monkeypatch):  # noqa: ANN001
    job = _job("running", params={"conversation_id": "ctx-7"}, agent_id=AGENT_ID)

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {"id": str(job.id)}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    result = envelope["result"]
    assert result["kind"] == "task"
    assert result["id"] == str(job.id)
    assert result["status"]["state"] == "working"
    assert result["contextId"] == "ctx-7"


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{}, {"id": ""}, {"id": "not-a-uuid"}])
async def test_tasks_get_rejects_bad_id(params):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": params}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)
    assert envelope["error"]["code"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_tasks_get_maps_missing_job_to_task_not_found(monkeypatch):  # noqa: ANN001
    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        raise NotFoundError("生成任务不存在")

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {"id": str(uuid4())}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert envelope["error"]["code"] == server_mod.TASK_NOT_FOUND


@pytest.mark.asyncio
async def test_tasks_cancel_returns_canceled_task(monkeypatch):  # noqa: ANN001
    job_id = uuid4()
    owned = _job("running", job_id=job_id, agent_id=AGENT_ID)

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return owned

    class _FakeJobService:
        def __init__(self, _db, _ctx) -> None:
            pass

        async def cancel_job(self, _job_id):
            return SimpleNamespace(id=job_id, status=SimpleNamespace(value="cancelled"), params={"conversation_id": "c1"})

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    monkeypatch.setattr(server_svc, "GenerativeJobService", _FakeJobService)
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/cancel", "params": {"id": str(job_id)}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    result = envelope["result"]
    assert result["kind"] == "task"
    assert result["status"]["state"] == "canceled"
    assert result["contextId"] == "c1"


@pytest.mark.asyncio
async def test_tasks_cancel_maps_terminal_job_to_not_cancelable(monkeypatch):  # noqa: ANN001
    job_id = uuid4()
    owned = _job("success", job_id=job_id, agent_id=AGENT_ID)

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return owned

    class _FakeJobService:
        def __init__(self, _db, _ctx) -> None:
            pass

        async def cancel_job(self, _job_id):
            raise BadRequestError("任务已结束，无法取消")

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    monkeypatch.setattr(server_svc, "GenerativeJobService", _FakeJobService)
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/cancel", "params": {"id": str(job_id)}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert envelope["error"]["code"] == server_mod.TASK_NOT_CANCELABLE


@pytest.mark.asyncio
async def test_tasks_cancel_hides_task_of_other_agent(monkeypatch):  # noqa: ANN001
    """同租户另一个智能体的 key 不能取消本智能体任务。"""
    job_id = uuid4()
    foreign = _job("running", job_id=job_id, agent_id=uuid4())

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return foreign

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/cancel", "params": {"id": str(job_id)}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert envelope["error"]["code"] == server_mod.TASK_NOT_FOUND


@pytest.mark.asyncio
async def test_unimplemented_task_method_is_method_not_found():
    """``tasks/resubscribe`` 等未实现方法一律方法未找到，不静默成功。"""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {"id": str(uuid4())}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)
    assert envelope["error"]["code"] == server_mod.METHOD_NOT_FOUND


@pytest.mark.asyncio
async def test_tasks_get_exposes_artifacts_for_succeeded_job(monkeypatch):  # noqa: ANN001
    """成功任务把产物映射为 ``Task.artifacts``，对端据此拿到（需鉴权的）下载地址。"""
    job = _job(
        "success",
        params={"conversation_id": "c1"},
        result={"kind": "image", "attachment_ids": ["att-1"], "mime_type": "image/png"},
        agent_id=AGENT_ID,
    )

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {"id": str(job.id)}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    result = envelope["result"]
    assert result["status"]["state"] == "completed"
    assert result["artifacts"][0]["parts"][0]["file"]["uri"].startswith(f"{BASE}/api/v1/open/a2a/agents/{AGENT_ID}/tasks/")


@pytest.mark.asyncio
async def test_tasks_get_omits_artifacts_while_running(monkeypatch):  # noqa: ANN001
    job = _job("running", params={}, result=None, agent_id=AGENT_ID)

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {"id": str(job.id)}}
    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert "artifacts" not in envelope["result"]


# --- 5. 产物下载归属校验 ------------------------------------------------------


def _artifact_job(*, agent_id, attachments=("att-1",)):
    return _job(
        "success",
        job_id=uuid4(),
        result={"kind": "image", "attachment_ids": list(attachments), "mime_type": "image/png"},
        agent_id=agent_id,
    )


@pytest.mark.asyncio
async def test_read_task_artifact_returns_bytes_for_own_task(monkeypatch):  # noqa: ANN001
    attachment_id = uuid4()
    job = _artifact_job(agent_id=AGENT_ID, attachments=(str(attachment_id),))

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    class _FakeAttachments:
        def __init__(self, _db, _ctx) -> None:
            pass

        async def read_attachment_bytes(self, _attachment_id):  # noqa: ANN001
            return b"PNGDATA", "image/png", "a.png"

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    monkeypatch.setattr(server_svc, "AttachmentService", _FakeAttachments)

    data, mime, filename = await server_svc.read_task_artifact(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, job.id, attachment_id)
    assert (data, mime, filename) == (b"PNGDATA", "image/png", "a.png")


@pytest.mark.asyncio
async def test_read_task_artifact_hides_task_of_other_agent(monkeypatch):  # noqa: ANN001
    """跨智能体取产物必须 404（而非 403）：不向对端确认该任务是否存在。"""
    attachment_id = uuid4()
    job = _artifact_job(agent_id=uuid4(), attachments=(str(attachment_id),))

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)

    with pytest.raises(NotFoundError):
        await server_svc.read_task_artifact(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, job.id, attachment_id)


@pytest.mark.asyncio
async def test_read_task_artifact_rejects_attachment_outside_task_result(monkeypatch):  # noqa: ANN001
    """只有该任务的产物可下载：否则用户凭 key 能取同租户任意附件。"""
    job = _artifact_job(agent_id=AGENT_ID, attachments=("att-1",))

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)

    with pytest.raises(NotFoundError):
        await server_svc.read_task_artifact(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, job.id, uuid4())


@pytest.mark.asyncio
async def test_read_task_artifact_rejects_non_agent_task(monkeypatch):  # noqa: ANN001
    """工作流节点等非智能体发起的任务不属于任何智能体，不对外暴露。"""
    attachment_id = uuid4()
    job = _job("success", job_id=uuid4(), result={"kind": "image", "attachment_ids": [str(attachment_id)]})

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)

    with pytest.raises(NotFoundError):
        await server_svc.read_task_artifact(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, job.id, attachment_id)


# --- 6. message/stream --------------------------------------------------------


class _FakeSession:
    """``AsyncSessionLocal()`` 替身：流式生成器内部自开会话，测试须替换掉真实连接。"""

    def __init__(self) -> None:
        self.committed = 0
        self.rolled_back = 0
        self.closed = 0

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        # 让出控制权一次再记 closed：真实 ``AsyncSession.close()`` 会 await，若调用方
        # 在关闭期间 cancel 本任务（哨兵早于会话关闭入队时的真实时序），计数就不会增长
        # —— 这样「成功回合的会话必被关掉」成了可断言的回归不变量。
        await asyncio.sleep(0)
        self.closed += 1
        return False

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1


def _patch_session(monkeypatch, session: _FakeSession) -> None:  # noqa: ANN001
    monkeypatch.setattr(server_svc, "AsyncSessionLocal", lambda: session)


async def _collect(stream) -> list[dict]:  # noqa: ANN001
    """把 SSE 帧解回 JSON 信封，便于断言形状。"""
    frames: list[dict] = []
    async for frame in stream:
        assert frame.startswith("data: ")
        assert frame.endswith("\n\n")
        frames.append(json.loads(frame[len("data: ") : -2]))
    return frames


def _stream_params(text: str = "写点什么", context_id: str | None = None) -> dict:
    message: dict = {"parts": [{"kind": "text", "text": text}]}
    if context_id:
        message["contextId"] = context_id
    return {"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {"message": message}}


@pytest.mark.asyncio
async def test_open_stream_preflight_failure_returns_error_envelope():
    """未发布智能体必须在 SSE 开始前回普通 JSON：流一旦开始，错误只能塞进帧里。"""
    opened = await server_svc.open_a2a_stream(_Db(agent=None), SimpleNamespace(), AGENT_ID, _stream_params())

    assert isinstance(opened, dict)
    assert opened["error"]["code"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_open_stream_rejects_bad_params_before_streaming():
    opened = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params(text="   "))

    assert isinstance(opened, dict)
    assert opened["error"]["code"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_open_stream_rejects_missing_params_before_streaming():
    payload = {"jsonrpc": "2.0", "id": 1, "method": "message/stream"}
    opened = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload)

    assert isinstance(opened, dict)
    assert opened["error"]["code"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_open_stream_emits_task_then_increments_then_final(monkeypatch):  # noqa: ANN001
    """真流路由：首帧 Task、中间帧逐片增量、末帧 completed 且带完整回答。"""
    session = _FakeSession()
    _patch_session(monkeypatch, session)
    seen: dict = {}

    async def fake_chat(_db, _ctx, _agent_id, text, conversation_id=None, on_delta=None):  # noqa: ANN001
        seen["text"] = text
        seen["conversation_id"] = conversation_id
        await on_delta("甲")
        await on_delta("乙")
        return ChatResponse(answer="甲乙")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    db = _Db(agent=_agent())
    stream = await server_svc.open_a2a_stream(db, SimpleNamespace(), AGENT_ID, _stream_params(text="写点什么", context_id="ctx-7"))

    frames = await _collect(stream)
    results = [f["result"] for f in frames]

    assert all(f["jsonrpc"] == "2.0" and f["id"] == 1 for f in frames)
    assert results[0]["kind"] == "task"
    assert results[0]["status"]["state"] == "working"
    assert results[0]["contextId"] == "ctx-7"

    mids = results[1:-1]
    assert [m["status"]["message"]["parts"][0]["text"] for m in mids] == ["甲", "乙"]
    assert all(m["final"] is False for m in mids)
    assert all(m["taskId"] == results[0]["id"] for m in mids)

    last = results[-1]
    assert last["final"] is True
    assert last["status"]["state"] == "completed"
    assert last["status"]["message"]["parts"][0]["text"] == "甲乙"

    assert seen["text"] == "写点什么"
    assert seen["conversation_id"] == "ctx-7"
    assert session.committed == 1
    # 成功回合的会话必须被正常关闭（回归：哨兵若早于 __aexit__ 入队，生成器会在
    # close 让出控制权时 cancel 掉本任务，closed 就不会增长）
    assert session.closed == 1
    # 前置校验的请求级事务已就地结束，不占着连接陪跑整条 SSE
    assert db.committed == 1
    # 必须是 commit 而非 rollback：鉴权依赖在同一会话里 flush 了 API Key 的
    # last_used_at（touch_last_used 由调用方提交），rollback 会让流式调用永不更新该字段
    assert db.rolled_back == 0


@pytest.mark.asyncio
async def test_open_stream_generates_context_id_when_absent(monkeypatch):  # noqa: ANN001
    """首轮未带 contextId 时生成一个并作为 conversation_id 下传，多轮才接得上。"""
    _patch_session(monkeypatch, _FakeSession())
    seen: dict = {}

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        seen["conversation_id"] = conversation_id
        return ChatResponse(answer="好的")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    results = [f["result"] for f in await _collect(stream)]

    assert seen["conversation_id"]
    assert results[0]["contextId"] == seen["conversation_id"]


@pytest.mark.asyncio
async def test_open_stream_one_shot_route_only_has_final_frame(monkeypatch):  # noqa: ANN001
    """不接 on_delta 的路由（flow/子智能体等）不产生中间帧，靠末帧一次给全。"""
    _patch_session(monkeypatch, _FakeSession())

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        return ChatResponse(answer="完整回答")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    results = [f["result"] for f in await _collect(stream)]

    assert len(results) == 2
    assert results[0]["kind"] == "task"
    assert results[-1]["status"]["state"] == "completed"
    assert results[-1]["status"]["message"]["parts"][0]["text"] == "完整回答"


@pytest.mark.asyncio
async def test_open_stream_maps_compliance_block_to_rejected(monkeypatch):  # noqa: ANN001
    """输入/输出合规拦截回 rejected（拒绝处理），并把原因交给对端。"""
    session = _FakeSession()
    _patch_session(monkeypatch, session)

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        await on_delta("部分")
        raise BadRequestError("输出内容包含敏感词，已拦截：测试")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    results = [f["result"] for f in await _collect(stream)]
    last = results[-1]

    assert last["final"] is True
    assert last["status"]["state"] == "rejected"
    assert "敏感词" in last["status"]["message"]["parts"][0]["text"]
    assert session.rolled_back == 1


@pytest.mark.asyncio
async def test_open_stream_maps_execution_failure_to_failed(monkeypatch):  # noqa: ANN001
    _patch_session(monkeypatch, _FakeSession())

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    last = [f["result"] for f in await _collect(stream)][-1]

    assert last["final"] is True
    assert last["status"]["state"] == "failed"
    assert "boom" in last["status"]["message"]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_open_stream_hands_off_job_id_via_metadata(monkeypatch):  # noqa: ANN001
    """产生异步生成任务时以 working/final 收尾，并给出真实 job id 供对端轮询。"""
    _patch_session(monkeypatch, _FakeSession())

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        return ChatResponse(answer="正在生成", generative_jobs=[{"id": "job-1", "kind": "video", "status": "pending"}])

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    last = [f["result"] for f in await _collect(stream)][-1]

    assert last["final"] is True
    assert last["status"]["state"] == "working"
    assert last["status"]["message"]["metadata"] == {"a2aJobTaskId": "job-1"}


@pytest.mark.asyncio
async def test_open_stream_cancels_chat_when_consumer_disconnects(monkeypatch):  # noqa: ANN001
    """客户端断连即取消对话任务：否则 LLM 调用会跑到底白烧 token。"""
    _patch_session(monkeypatch, _FakeSession())
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return ChatResponse(answer="不会到这里")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    # 只取首帧 Task 便退出 —— 模拟客户端拿到流后断开
    first = await anext(stream)
    assert json.loads(first[len("data: ") : -2])["result"]["kind"] == "task"
    await started.wait()

    await stream.aclose()
    await asyncio.wait_for(cancelled.wait(), timeout=1)


@pytest.mark.asyncio
async def test_run_published_agent_chat_forwards_on_delta(monkeypatch):  # noqa: ANN001
    """``on_delta`` 必须一路透传到 ``AgentService.chat``。

    整条真流链路就靠这一行透传；其余流式用例都 monkeypatch 掉了本函数，断了不会有人发现。
    """
    seen: dict = {}

    class _FakeAgentService:
        def __init__(self, _db, _ctx) -> None:  # noqa: ANN001
            pass

        async def chat(self, agent_id, body, *, on_delta=None):  # noqa: ANN001
            seen["agent_id"] = agent_id
            seen["body"] = body
            seen["on_delta"] = on_delta
            return ChatResponse(answer="好")

    monkeypatch.setattr("miles_portal.tenant.agents.services.agent.AgentService", _FakeAgentService)

    async def cb(_piece: str) -> None:  # noqa: ANN202
        return None

    response = await server_svc.run_published_agent_chat(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, "写点什么", conversation_id="ctx-1", on_delta=cb)

    assert response.answer == "好"
    assert seen["agent_id"] == AGENT_ID
    assert seen["body"].query == "写点什么"
    assert seen["body"].conversation_id == "ctx-1"
    assert seen["on_delta"] is cb


@pytest.mark.asyncio
async def test_open_stream_increment_with_special_chars_stays_single_line(monkeypatch):  # noqa: ANN001
    """增量含换行与引号时，SSE 帧仍须是单行合法 JSON —— 对端按行切帧，裸换行会截断。"""
    _patch_session(monkeypatch, _FakeSession())
    piece = '第一行\n第二行 "引号" \\ 反斜杠'

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        await on_delta(piece)
        return ChatResponse(answer=piece)

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    raw = [frame async for frame in stream]
    body = raw[1][len("data: ") : -2]

    assert raw[1].startswith("data: ") and raw[1].endswith("\n\n")
    # 正文里的换行必须被 JSON 转义：裸换行会让对端按行切帧时截断
    assert "\n" not in body
    assert json.loads(body)["result"]["status"]["message"]["parts"][0]["text"] == piece


@pytest.mark.asyncio
async def test_open_stream_skips_empty_delta_pieces(monkeypatch):  # noqa: ANN001
    """空片不发帧（与 ws 侧同判定）：否则末帧前会多出若干个空文本增量帧。"""
    _patch_session(monkeypatch, _FakeSession())

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        await on_delta("")
        await on_delta("甲")
        await on_delta("")
        return ChatResponse(answer="甲")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    results = [f["result"] for f in await _collect(stream)]

    assert len(results) == 3  # Task + 一个增量帧 + 末帧
    assert results[1]["status"]["message"]["parts"][0]["text"] == "甲"


@pytest.mark.asyncio
async def test_open_stream_emits_heartbeat_while_waiting_for_first_delta(monkeypatch):  # noqa: ANN001
    """长时间无增量时发 SSE 注释帧：否则对端与中间代理会在 idle 超时后掐断连接。

    一次性路由（tool_agent / flow / 子智能体）在末帧之前可能几分钟不产出任何字节 ——
    这正是这条的必要性所在，对端拿不到心跳只能判定连接已死。
    """
    _patch_session(monkeypatch, _FakeSession())
    monkeypatch.setattr(server_svc, "SSE_HEARTBEAT_SECONDS", 0.01, raising=False)

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        await asyncio.sleep(0.05)
        return ChatResponse(answer="慢回答")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    raw = [frame async for frame in stream]

    assert any(frame.startswith(":") for frame in raw)
    # 心跳不改变数据帧序列：仍是「首帧 Task + 末帧终态」，且心跳不得混进 JSON 帧
    data = [json.loads(f[len("data: ") : -2]) for f in raw if f.startswith("data: ")]
    assert data[0]["result"]["kind"] == "task"
    assert data[-1]["result"]["final"] is True
    assert data[-1]["result"]["status"]["state"] == "completed"


@pytest.mark.asyncio
async def test_open_stream_reports_failed_when_session_cannot_open(monkeypatch):  # noqa: ANN001
    """连会话都开不起来时也要回终态帧：否则对端只看到 Task 帧后流自然结束，只能等超时。"""

    def boom():  # noqa: ANN202
        raise RuntimeError("engine unavailable")

    monkeypatch.setattr(server_svc, "AsyncSessionLocal", boom)

    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())
    results = [f["result"] for f in await _collect(stream)]

    assert results[0]["kind"] == "task"
    assert results[-1]["final"] is True
    assert results[-1]["status"]["state"] == "failed"
