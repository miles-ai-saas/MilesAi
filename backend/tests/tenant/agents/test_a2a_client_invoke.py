"""A2A 出站调用的响应分类：``error`` / ``Task`` / ``Message``。

``invoke_a2a_peer`` 此前把「这次调用成功还是失败」交给 ``_extract_text_from_response``
（一个尽可能榨出文本的宽容函数）决定，于是对端的 JSON-RPC ``error`` 会被当作它的
「回答」写进主模型素材。本文件锁定修正后的分类链。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from miles_common.exceptions import BadRequestError
from miles_portal.tenant.a2a import client as client_mod


class _Resp:
    def __init__(self, data: dict, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code

    def json(self) -> dict:  # noqa: D102
        return self._data


class _SeqClient:
    """按调用顺序返回响应的 httpx.AsyncClient 替身；响应耗尽后重复末项。

    重复末项让「一直 working 直到超时」这类用例不必预先生成几十个响应。
    """

    def __init__(self, responses: list[dict], captured: list[dict]) -> None:
        self._responses = list(responses)
        self._captured = captured

    async def __aenter__(self) -> _SeqClient:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> _Resp:
        self._captured.append({"url": url, "body": json})
        index = min(len(self._captured) - 1, len(self._responses) - 1)
        return _Resp(self._responses[index])


def _patch(monkeypatch, responses: list[dict]) -> list[dict]:  # noqa: ANN001
    captured: list[dict] = []
    monkeypatch.setattr(
        client_mod.httpx,
        "AsyncClient",
        lambda **_kwargs: _SeqClient(responses, captured),
    )
    return captured


def _peer() -> SimpleNamespace:
    return SimpleNamespace(
        name="Peer",
        status=SimpleNamespace(value="active"),
        agent_card_json={"additionalInterfaces": [{"url": "https://peer.example.com/a2a", "transport": "JSONRPC"}]},
        base_url="https://peer.example.com",
        agent_card_url="https://peer.example.com/.well-known/agent-card.json",
        card_display_name="Peer",
        auth_config=None,
    )


def _task(state: str, *, task_id: str = "j1", artifacts=None, progress: str | None = None, percent: int | None = None) -> dict:
    status: dict = {"state": state, "timestamp": "2026-01-02T03:04:05+00:00"}
    if progress is not None:
        status["message"] = {"kind": "message", "role": "agent", "messageId": "m1", "parts": [{"kind": "text", "text": progress}]}
        if percent is not None:
            status["message"]["metadata"] = {"percent": percent}
    body: dict = {"kind": "task", "id": task_id, "status": status}
    if artifacts is not None:
        body["artifacts"] = artifacts
    return body


@pytest.mark.asyncio
async def test_jsonrpc_error_raises_instead_of_masquerading_as_answer(monkeypatch):  # noqa: ANN001
    """对端协议级错误必须抛错，而不是变成「它回答了这句话」。"""
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "error": {"code": -32602, "message": "参数错误"}}])

    with pytest.raises(BadRequestError) as excinfo:
        await client_mod.invoke_a2a_peer(_peer(), "你好")

    assert "-32602" in str(excinfo.value)
    assert "参数错误" in str(excinfo.value)
    # 收到结构正确的 JSON-RPC error 说明 endpoint 形态已匹配：不得再探测第二个
    assert len(captured) == 1


def _artifact(name: str | None = "image-1", mime: str | None = "image/png", uri: str | None = "https://peer.example.com/dl/a1") -> dict:
    file: dict = {}
    if name is not None:
        file["name"] = name
    if mime is not None:
        file["mimeType"] = mime
    if uri is not None:
        file["uri"] = uri
    return {"artifactId": "att-1", "parts": [{"kind": "file", "file": file}]}


def test_task_state_reads_nested_state():
    assert client_mod._task_state({"status": {"state": "working"}}) == "working"
    assert client_mod._task_state({"status": {}}) is None
    assert client_mod._task_state({"status": "not-a-dict"}) is None
    assert client_mod._task_state({}) is None


def test_looks_like_task_uses_structure_not_kind():
    """老 peer 不一定带 ``kind``，判据必须落在 ``status.state`` 上。"""
    assert client_mod._looks_like_task({"result": {"status": {"state": "working"}}}) is True
    assert client_mod._looks_like_task({"result": {"kind": "task"}}) is False
    assert client_mod._looks_like_task({"result": {"text": "hi"}}) is False
    assert client_mod._looks_like_task("plain") is False


def test_render_completed_task_lists_artifact_refs():
    out = client_mod._render_agent_task(_task("completed", artifacts=[_artifact()]))

    assert out.splitlines()[0] == "外部任务已完成"
    assert "image-1" in out and "image/png" in out
    assert "https://peer.example.com/dl/a1" in out
    assert "任务 ID：j1" in out


def test_render_artifact_without_uri_is_marked():
    out = client_mod._render_agent_task(_task("completed", artifacts=[_artifact(uri=None)]))

    assert "无下载地址" in out


def test_render_uses_artifact_id_when_name_absent():
    out = client_mod._render_agent_task(_task("completed", artifacts=[_artifact(name=None)]))

    assert "att-1" in out


def test_render_failed_task_shows_progress_text():
    out = client_mod._render_agent_task(_task("failed", progress="模型拒绝生成"))

    assert out.splitlines()[0] == "外部任务失败"
    assert "进展：模型拒绝生成" in out


@pytest.mark.parametrize(
    ("state", "headline"),
    [
        ("canceled", "外部任务已取消"),
        ("rejected", "外部任务被拒绝"),
        ("input-required", "外部任务需要补充输入"),
        ("auth-required", "外部任务需要鉴权"),
        ("working", "外部任务仍在进行（状态：working）"),
        ("unknown", "外部任务状态未知（状态：unknown）"),
    ],
)
def test_render_headline_by_state(state, headline):  # noqa: ANN001
    assert client_mod._render_agent_task(_task(state)).splitlines()[0] == headline


def test_render_appends_note_when_present():
    out = client_mod._render_agent_task(_task("working"), note="已等待 60 秒")

    assert out.splitlines()[-1] == "已等待 60 秒"


def test_stop_polling_states_cover_terminal_and_interrupted():
    """中断态必须停止轮询：对端在等我们补输入/凭证，继续轮询只会白等。"""
    assert client_mod.STOP_POLLING_TASK_STATES == client_mod.TERMINAL_TASK_STATES | client_mod.INTERRUPTED_TASK_STATES
    assert "input-required" in client_mod.STOP_POLLING_TASK_STATES
    assert "auth-required" in client_mod.STOP_POLLING_TASK_STATES
    assert "working" not in client_mod.STOP_POLLING_TASK_STATES


def _fast_poll(monkeypatch) -> None:  # noqa: ANN001
    """把轮询压到亚毫秒级：测试不该真的睡 60 秒。

    ``_resolve_agent_task`` 在运行时读模块常量，故 monkeypatch 生效。
    """
    monkeypatch.setattr(client_mod, "TASK_POLL_INTERVAL_SECONDS", 0.001)
    monkeypatch.setattr(client_mod, "TASK_POLL_TIMEOUT_SECONDS", 0.02)


@pytest.mark.asyncio
async def test_terminal_task_is_not_polled(monkeypatch):  # noqa: ANN001
    """对端可能同步就绪：已是终态时一次多余请求都不发。"""
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "result": _task("completed", artifacts=[_artifact()])}])
    monkeypatch.setattr(client_mod, "TASK_POLL_INTERVAL_SECONDS", 2.0)

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert "外部任务已完成" in answer
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_polls_until_completed_and_reports_artifacts(monkeypatch):  # noqa: ANN001
    _fast_poll(monkeypatch)
    captured = _patch(
        monkeypatch,
        [
            {"jsonrpc": "2.0", "id": "1", "result": _task("working")},
            {"jsonrpc": "2.0", "id": "2", "result": _task("working", progress="45% 渲染中", percent=45)},
            {"jsonrpc": "2.0", "id": "3", "result": _task("completed", artifacts=[_artifact(name="封面", mime="image/png")])},
        ],
    )

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert "外部任务已完成" in answer
    assert "封面" in answer and "image/png" in answer
    # 首次 message/send + 两次 tasks/get
    assert len(captured) == 3
    assert captured[1]["body"]["method"] == "tasks/get"
    assert captured[1]["body"]["params"] == {"id": "j1"}


@pytest.mark.asyncio
async def test_polls_with_symmetric_endpoint(monkeypatch):  # noqa: ANN001
    """``message/send`` 探到哪个形态，``tasks/get`` 就打对应的那一个。"""
    _fast_poll(monkeypatch)
    captured = _patch(
        monkeypatch,
        [
            {"jsonrpc": "2.0", "id": "1", "result": _task("working")},
            {"jsonrpc": "2.0", "id": "2", "result": _task("completed")},
        ],
    )

    await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert captured[0]["url"] == "https://peer.example.com/a2a/message/send"
    assert captured[1]["url"] == "https://peer.example.com/a2a/tasks/get"


@pytest.mark.asyncio
async def test_timeout_returns_snapshot_with_task_id(monkeypatch):  # noqa: ANN001
    _fast_poll(monkeypatch)
    _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "result": _task("working", progress="45% 渲染中")}])

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert answer.splitlines()[0] == "外部任务仍在进行（状态：working）"
    assert "任务 ID：j1" in answer
    assert "已等待" in answer


@pytest.mark.asyncio
async def test_input_required_stops_polling(monkeypatch):  # noqa: ANN001
    """中断态不再轮询：对端在等我们补输入，白等到超时毫无意义。"""
    _fast_poll(monkeypatch)
    captured = _patch(
        monkeypatch,
        [
            {"jsonrpc": "2.0", "id": "1", "result": _task("working")},
            {"jsonrpc": "2.0", "id": "2", "result": _task("input-required", progress="请补充视频时长")},
        ],
    )

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一段视频")

    assert answer.splitlines()[0] == "外部任务需要补充输入"
    assert "请补充视频时长" in answer
    assert len(captured) == 2


@pytest.mark.asyncio
async def test_poll_jsonrpc_error_falls_back_to_snapshot(monkeypatch):  # noqa: ANN001
    """对端不支持 tasks/get（``-32601``）时回退到最后一次已知状态，而不是抛给上层。"""
    _fast_poll(monkeypatch)
    _patch(
        monkeypatch,
        [
            {"jsonrpc": "2.0", "id": "1", "result": _task("working")},
            {"jsonrpc": "2.0", "id": "2", "error": {"code": -32601, "message": "不支持的方法"}},
        ],
    )

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert "继续查询失败" in answer
    assert "-32601" in answer and "不支持的方法" in answer
    assert "任务 ID：j1" in answer


@pytest.mark.asyncio
async def test_poll_request_longer_than_remaining_budget_returns_waited_snapshot(monkeypatch):  # noqa: ANN001
    """单次 ``tasks/get`` 也受剩余预算约束：请求慢于预算 → 「已等待」快照，而非网络异常或挂死。

    预算只 cap 睡眠的话，请求自身还能再吃掉 httpx 的 60s，一轮最坏 ~120s。
    """
    _fast_poll(monkeypatch)
    captured: list[dict] = []
    completed: list[bool] = []

    class _Slow(_SeqClient):
        async def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> _Resp:
            captured.append({"url": url, "body": json})
            if len(captured) > 1:
                # 预算 ~0.02s，请求睡 0.05s：只有被预算取消，这行之后才走不到。
                await asyncio.sleep(0.05)
                completed.append(True)
            return _Resp({"jsonrpc": "2.0", "id": "1", "result": _task("working")})

    monkeypatch.setattr(client_mod.httpx, "AsyncClient", lambda **_kwargs: _Slow([], captured))

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert completed == []
    assert "已等待" in answer
    assert "网络异常" not in answer
    assert "响应非 JSON" not in answer
    assert "任务 ID：j1" in answer


@pytest.mark.asyncio
async def test_poll_network_error_does_not_retry_second_endpoint(monkeypatch):  # noqa: ANN001
    """轮询内部异常不得冒泡到 endpoint 循环 —— 否则会对第二个端点重跑一遍整段轮询。"""
    _fast_poll(monkeypatch)
    captured: list[dict] = []

    class _Boom(_SeqClient):
        async def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> _Resp:
            captured.append({"url": url, "body": json})
            if len(captured) == 1:
                return _Resp({"jsonrpc": "2.0", "id": "1", "result": _task("working")})
            raise client_mod.httpx.RequestError("boom")

    monkeypatch.setattr(client_mod.httpx, "AsyncClient", lambda **_kwargs: _Boom([], captured))

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert "继续查询失败（网络异常）" in answer
    # 只有 message/send + 一次 tasks/get：第二个端点未被重试
    assert [item["url"] for item in captured] == [
        "https://peer.example.com/a2a/message/send",
        "https://peer.example.com/a2a/tasks/get",
    ]


@pytest.mark.asyncio
async def test_task_without_id_is_not_polled(monkeypatch):  # noqa: ANN001
    _fast_poll(monkeypatch)
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "result": _task("working", task_id=None)}])

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert "对端未给出任务 ID" in answer
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_terminal_task_without_id_is_not_told_it_cannot_be_polled(monkeypatch):  # noqa: ANN001
    """已停止轮询态缺 ``id`` 不该报「无法继续查询」：本就不需要继续查询。"""
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "result": _task("completed", task_id=None)}])

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert answer.splitlines()[0] == "外部任务已完成"
    assert "对端未给出任务 ID" not in answer
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_message_response_is_not_treated_as_task(monkeypatch):  # noqa: ANN001
    """回归：``Message`` 响应不被 Task 分流误捕，抽取行为与改动前逐字一致。

    plan 原文此处断言 ``answer == "收到"``。但 ``_extract_text_from_response`` 并不认识
    「顶层 ``Message`` 的 ``parts``」这一形状（它只认 ``result`` 的四个文本键与
    ``result.message.parts``），BASE 上该形状的既有输出就是 ``str(result)``。spec §3.1
    明确本批**冻结**该函数，§6 又要求「``Message`` 响应的既有解析行为无回归」，故这里锁定
    改动前的真实行为；「顶层 ``Message`` 抽不出文本」是既有缺口，不在本任务范围。
    """
    result = {"kind": "message", "role": "agent", "parts": [{"kind": "text", "text": "收到"}]}
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "result": result}])

    answer = await client_mod.invoke_a2a_peer(_peer(), "你好")

    # 不是 Task 渲染结果：若被 Task 分流误捕，这里会变成「外部任务状态未知（状态：unknown）」
    assert answer == str(result)
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_cancel_peer_task_sends_tasks_cancel(monkeypatch):  # noqa: ANN001
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "result": _task("canceled")}])

    await client_mod.cancel_a2a_peer_task(_peer(), "j1")

    assert len(captured) == 1
    assert captured[0]["url"] == "https://peer.example.com/a2a/tasks/cancel"
    assert captured[0]["body"]["method"] == "tasks/cancel"
    assert captured[0]["body"]["params"] == {"id": "j1"}


@pytest.mark.asyncio
async def test_cancel_peer_task_raises_on_not_cancelable(monkeypatch):  # noqa: ANN001
    """对端明确拒绝时抛错，且不再探测第二个 endpoint（它已应答，形态已匹配）。"""
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "error": {"code": -32002, "message": "任务已结束"}}])

    with pytest.raises(BadRequestError) as excinfo:
        await client_mod.cancel_a2a_peer_task(_peer(), "j1")

    assert "-32002" in str(excinfo.value)
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_cancel_peer_task_tries_both_endpoints_before_giving_up(monkeypatch):  # noqa: ANN001
    """HTTP 层失败可能只是路径不对：两个形态都试过才认输。"""
    captured: list[dict] = []

    class _AllFail(_SeqClient):
        async def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> _Resp:
            captured.append({"url": url, "body": json})
            return _Resp({}, status_code=500)

    monkeypatch.setattr(client_mod.httpx, "AsyncClient", lambda **_kwargs: _AllFail([], captured))

    with pytest.raises(BadRequestError):
        await client_mod.cancel_a2a_peer_task(_peer(), "j1")

    assert [item["url"] for item in captured] == [
        "https://peer.example.com/a2a/tasks/cancel",
        "https://peer.example.com/a2a",
    ]


@pytest.mark.asyncio
async def test_cancel_peer_task_rejects_inactive_peer(monkeypatch):  # noqa: ANN001
    peer = _peer()
    peer.status = SimpleNamespace(value="inactive")

    with pytest.raises(BadRequestError):
        await client_mod.cancel_a2a_peer_task(peer, "j1")
