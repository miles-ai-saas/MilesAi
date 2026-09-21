"""A2A 出站调用的响应分类：``error`` / ``Task`` / ``Message``。

``invoke_a2a_peer`` 此前把「这次调用成功还是失败」交给 ``_extract_text_from_response``
（一个尽可能榨出文本的宽容函数）决定，于是对端的 JSON-RPC ``error`` 会被当作它的
「回答」写进主模型素材。本文件锁定修正后的分类链。
"""

from __future__ import annotations

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
