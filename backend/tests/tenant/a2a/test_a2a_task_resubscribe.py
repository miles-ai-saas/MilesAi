"""A2A ``tasks/resubscribe`` 服务层：帧序列、去重、安全上限、断连留痕。

只覆盖订阅用例本身：订阅循环在 ``tests/tenant/generative/test_job_watch.py``，
纯逻辑在 ``test_a2a_server_card.py``。此处把 watcher 换成脚本化假实现，
从而精确控制「第几帧发生什么」。
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import NotFoundError
from miles_core.models.agent import Agent, AgentStatus, AgentType
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a import server as server_mod
from miles_portal.tenant.a2a.server import A2A_PUBLISH_FLAG
from miles_portal.tenant.a2a.services import audit as audit_svc
from miles_portal.tenant.a2a.services import server as server_svc
from miles_portal.tenant.a2a.services import subscription as subscription_svc

AGENT_ID = uuid4()
ATTACHMENT_ID = uuid4()
BASE = "https://miles.example.com"
JOB_ID = uuid4()


def _ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="a2a-peer",
        is_superuser=False,
        permissions=frozenset({"agent:read"}),
        auth_via="api_key",
        api_key_id=uuid4(),
    )


def _agent():
    agent = Agent()
    agent.id = AGENT_ID
    agent.name = "客服助手"
    agent.description = "D"
    agent.agent_type = AgentType.CUSTOM
    agent.status = AgentStatus.ENABLED
    agent.config = {A2A_PUBLISH_FLAG: True}
    agent.deleted_at = None
    return agent


class _Db:
    """最小 fake：``get`` 返回预置智能体，``commit`` 计数。"""

    def __init__(self, agent=None):  # noqa: ANN001
        self._agent = agent
        self.committed = 0

    async def get(self, _model, _id):  # noqa: ANN001
        return self._agent

    async def commit(self):  # noqa: ANN001
        self.committed += 1


def _job(status: str, *, progress_message=None, progress_percent=None, result=None, params=None):  # noqa: ANN001, ANN202
    """生成任务替身：订阅用例只用这几个字段。"""
    return SimpleNamespace(
        id=JOB_ID,
        tenant_id=uuid4(),
        status=SimpleNamespace(value=status),
        progress_message=progress_message,
        progress_percent=progress_percent,
        result=result,
        params=params if params is not None else {},
    )


def _params(*, task_id=JOB_ID, method="tasks/resubscribe") -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": {"id": str(task_id)}}


def _scripted(script):  # noqa: ANN001, ANN202
    """把「任务快照 / None / 异常」的脚本变成假的 ``watch_generative_job``。"""

    async def fake(**_kwargs):  # noqa: ANN003
        for item in script:
            if isinstance(item, Exception):
                raise item
            yield item

    return fake


async def _raw_frames(stream) -> list[str]:  # noqa: ANN001
    return [frame async for frame in stream]


async def _json_frames(stream) -> list[dict]:  # noqa: ANN001
    """只取数据帧（保活帧是 SSE 注释行，不进 JSON 序列）。"""
    return [json.loads(f[len("data: ") : -2]) for f in await _raw_frames(stream) if f.startswith("data: ")]


@pytest.fixture(autouse=True)
def audit_recorder(monkeypatch):  # noqa: ANN001
    """审计走独立会话，单测不连库：替换 ``subscription`` 命名空间里的写入函数。"""
    recorded: list[dict] = []

    async def fake_write(**kwargs):  # noqa: ANN003
        # 让出一次控制权：真实写库必然挂起，取消时序的敏感性只有这样才测得出来
        await asyncio.sleep(0)
        recorded.append(kwargs)

    monkeypatch.setattr(subscription_svc, "write_a2a_audit", fake_write)
    return recorded


@pytest.fixture
def owned_job(monkeypatch):  # noqa: ANN001
    """让归属校验通过：``load_owned_agent_task`` 取到一个属于本智能体的任务。"""

    def _set(job):  # noqa: ANN001
        job.source_ref_type = "agent"
        job.source_ref_id = AGENT_ID

        async def _get(_db, _ctx, _job_id):  # noqa: ANN001
            return job

        # 打的是 server 模块的命名空间：归属校验函数定义在那里
        monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", _get)
        return job

    return _set


# --- 前置校验 --------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_preflight_rejects_unpublished_agent_and_audits_failure(audit_recorder, monkeypatch):  # noqa: ANN001
    def fail_watch(**_kwargs):  # noqa: ANN003
        raise AssertionError("前置校验失败时不应搭起订阅循环")

    monkeypatch.setattr(subscription_svc, "watch_generative_job", fail_watch)

    opened = await subscription_svc.open_task_subscription(_Db(agent=None), _ctx(), AGENT_ID, _params(), base_url=BASE)

    assert isinstance(opened, dict)
    # 与 message/stream 的智能体门槛同口径：未发布回参数类错误码，而不是「任务不存在」
    assert opened["error"]["code"] == server_mod.INVALID_PARAMS
    assert len(audit_recorder) == 1
    assert audit_recorder[0]["action"] == server_mod.AUDIT_ACTION_TASKS_RESUBSCRIBE
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert audit_recorder[0]["detail"]["errorCode"] == server_mod.INVALID_PARAMS
    # 前置失败没有流，故 detail 里不该出现只有收流才有的时间线字段
    assert "endedBy" not in audit_recorder[0]["detail"]


@pytest.mark.asyncio
async def test_preflight_rejects_bad_task_id_and_audits_invalid_params(audit_recorder):  # noqa: ANN001
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {"id": "not-a-uuid"}}

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, payload, base_url=BASE)

    assert isinstance(opened, dict)
    assert opened["error"]["code"] == server_mod.INVALID_PARAMS
    assert audit_recorder[0]["detail"]["errorCode"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_preflight_rejects_foreign_or_missing_task_with_task_not_found(audit_recorder, owned_job, monkeypatch):  # noqa: ANN001
    """不属于该智能体、或根本不存在（含合成流式 id）：一律 ``-32001``，不确认任务是否存在。"""
    job = owned_job(_job("running"))
    job.source_ref_id = uuid4()

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    assert isinstance(opened, dict)
    assert opened["error"]["code"] == server_mod.TASK_NOT_FOUND
    assert audit_recorder[0]["detail"]["errorCode"] == server_mod.TASK_NOT_FOUND

    async def _missing(_db, _ctx, _job_id):  # noqa: ANN001
        raise NotFoundError("生成任务不存在")

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", _missing)

    missing = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(task_id=uuid4()), base_url=BASE)
    assert isinstance(missing, dict)
    assert missing["error"]["code"] == server_mod.TASK_NOT_FOUND
    assert len(audit_recorder) == 2
    assert audit_recorder[1]["detail"]["method"] == "tasks/resubscribe"


# --- 帧序列 ----------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_frames_follow_deduped_task_status_artifact_terminal(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """首帧 Task → 变化才发 status-update → 产物帧 → 终态帧（final=true）。"""
    job = owned_job(_job("running", progress_message="10%", params={"conversation_id": "ctx-7"}))
    done = _job(
        "success",
        progress_message="已完成",
        progress_percent=100,
        result={"attachment_id": str(ATTACHMENT_ID), "mime_type": "video/mp4", "kind": "video"},
    )
    script = [job, _job("running", progress_message="10%"), _job("running", progress_message="60%"), done]
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted(script))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    # 帧只消费一次：先收全，再分别从数据帧与注释帧里取断言素材
    raw = await _raw_frames(opened)
    results = [json.loads(f[len("data: ") : -2])["result"] for f in raw if f.startswith("data: ")]

    assert results[0]["kind"] == "task"
    assert results[0]["status"]["state"] == "working"
    assert results[0]["contextId"] == "ctx-7"
    assert "artifacts" not in results[0]

    mids = results[1:-2]
    assert [m["status"]["message"]["parts"][0]["text"] for m in mids] == ["60%"]
    assert mids[0]["final"] is False

    artifact = results[-2]
    assert artifact["kind"] == "artifact-update"
    assert artifact["artifact"]["artifactId"] == str(ATTACHMENT_ID)
    assert artifact["artifact"]["parts"][0]["file"]["uri"] == f"{BASE}/api/v1/open/a2a/agents/{AGENT_ID}/tasks/{JOB_ID}/artifacts/{ATTACHMENT_ID}"

    last = results[-1]
    assert last["kind"] == "status-update"
    assert last["status"]["state"] == "completed"
    assert last["final"] is True

    # 无变化的那一帧换成了保活注释帧
    assert any(frame.startswith(":") for frame in raw)

    await audit_svc.drain_pending_audits()
    assert len(audit_recorder) == 1
    assert audit_recorder[0]["detail"]["endedBy"] == "terminal"
    assert audit_recorder[0]["detail"]["taskState"] == "completed"
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_OK
    assert audit_recorder[0]["detail"]["taskId"] == str(JOB_ID)
    assert audit_recorder[0]["detail"]["contextId"] == "ctx-7"


@pytest.mark.asyncio
async def test_progress_frame_carries_percent_in_message_metadata(monkeypatch, owned_job):  # noqa: ANN001
    job = owned_job(_job("running", progress_message="渲染中", progress_percent=45))
    monkeypatch.setattr(
        subscription_svc,
        "watch_generative_job",
        _scripted([job, _job("running", progress_message="渲染中", progress_percent=46)]),
    )

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert results[1]["status"]["message"]["parts"][0]["text"] == "渲染中"
    assert results[1]["status"]["message"]["metadata"] == {"percent": 46}


@pytest.mark.asyncio
async def test_already_terminal_subscription_puts_artifacts_in_first_frame(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """订阅时已终态：产物挂首帧，且**不**再发 artifact-update（同一条流里不重复出现）。"""
    done = owned_job(
        _job(
            "success",
            progress_message="已完成",
            result={"attachment_ids": [str(ATTACHMENT_ID)], "mime_type": "image/png", "kind": "image"},
        )
    )
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([done]))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert [r["kind"] for r in results] == ["task", "status-update"]
    assert results[0]["artifacts"][0]["artifactId"] == str(ATTACHMENT_ID)
    assert results[-1]["final"] is True and results[-1]["status"]["state"] == "completed"

    await audit_svc.drain_pending_audits()
    assert audit_recorder[0]["detail"]["endedBy"] == "terminal"


@pytest.mark.asyncio
async def test_omits_context_id_when_unresolvable(monkeypatch, owned_job):  # noqa: ANN001
    """``contextId`` 解析不到就省略（对规范必填要求的有意偏离，见设计 §3.8）。"""
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([owned_job(_job("running", progress_message="跑着"))]))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert all("contextId" not in frame for frame in results)
    assert all("contextId" not in frame["status"].get("message", {}) for frame in results)


@pytest.mark.asyncio
async def test_safety_cap_closes_with_real_state_and_final(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """watcher 结束而任务仍未终态：以真实状态 + ``final=true`` 收流，不谎报 completed。"""
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([owned_job(_job("pending"))]))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert results[0]["status"]["state"] == "submitted"
    assert results[-1]["final"] is True
    assert results[-1]["status"]["state"] == "submitted"

    await audit_svc.drain_pending_audits()
    assert audit_recorder[0]["detail"]["endedBy"] == "safety-cap"
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_OK


@pytest.mark.asyncio
async def test_canceled_job_audits_ok_and_reports_task_state(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """任务被取消是合法终态：outcome 记 ``ok``（``canceled`` 这一 outcome 专指对端断连）。"""
    monkeypatch.setattr(
        subscription_svc,
        "watch_generative_job",
        _scripted([owned_job(_job("running")), _job("cancelled", progress_message="已取消")]),
    )

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert results[-1]["status"]["state"] == "canceled"

    await audit_svc.drain_pending_audits()
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_OK
    assert audit_recorder[0]["detail"]["taskState"] == "canceled"
    assert audit_recorder[0]["detail"]["endedBy"] == "terminal"


# --- 断连与异常 ------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_disconnect_audits_canceled_exactly_once(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """对端中途掐断连接：恰好一条 ``canceled`` 流水，且带断连前的状态。"""
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([owned_job(_job("running")), _job("running", progress_message="60%")]))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    assert await anext(opened) is not None  # 首帧 Task

    await opened.aclose()

    await audit_svc.drain_pending_audits()
    assert len(audit_recorder) == 1
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_CANCELED
    assert audit_recorder[0]["detail"]["endedBy"] == "disconnect"
    assert audit_recorder[0]["detail"]["taskState"] == "working"


@pytest.mark.asyncio
async def test_watcher_error_emits_failed_terminal_frame_and_audits(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """订阅中途的非预期异常（任务被删等）：回终态帧再收流，绝不无声断流。"""
    monkeypatch.setattr(
        subscription_svc,
        "watch_generative_job",
        _scripted([owned_job(_job("running")), RuntimeError("任务已被删除")]),
    )

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert results[-1]["final"] is True
    assert results[-1]["status"]["state"] == "failed"

    await audit_svc.drain_pending_audits()
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert audit_recorder[0]["detail"]["endedBy"] == "failed"


@pytest.mark.asyncio
async def test_first_item_tick_closes_stream_with_failed_audit(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """契约被改坏（首产出竟是空闲刻度）时按失败收尾：不成空流、不变成 500。"""
    # ``owned_job`` 是工厂式 fixture：不调用就只是**声明**了它，归属校验的 patch 不会落下，
    # 前置校验会拿假 DB 去撞真实取数。此处调用只为让前置校验通过（该任务快照本身用不到，
    # 脚本第一个产出是空闲刻度）。
    owned_job(_job("running"))
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([None]))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)

    assert await _json_frames(opened) == []

    await audit_svc.drain_pending_audits()
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert audit_recorder[0]["detail"]["endedBy"] == "failed"


@pytest.mark.asyncio
async def test_commit_releases_request_scoped_connection(monkeypatch, owned_job):  # noqa: ANN001
    """通过前置校验后立刻结束请求级事务：30 分钟的流不能让一条连接陪跑。"""
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([owned_job(_job("running"))]))
    db = _Db(agent=_agent())

    await subscription_svc.open_task_subscription(db, _ctx(), AGENT_ID, _params(), base_url=BASE)

    assert db.committed == 1
