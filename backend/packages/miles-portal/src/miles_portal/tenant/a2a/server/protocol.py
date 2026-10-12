"""A2A Task/Message/Artifact 与 JSON-RPC 信封构造（纯逻辑）。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from miles_common.exceptions import AppError
from miles_portal.tenant.a2a.server.card import a2a_task_artifact_path
from miles_portal.tenant.a2a.server.constants import (
    _TASKS_METHOD_PREFIX,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    TASK_NOT_FOUND,
)


def now_iso() -> str:
    """A2A ``TaskStatus.timestamp``（ISO 8601 / UTC）。"""
    return datetime.now(UTC).isoformat()


def progress_text(*, progress_message: object, percent: object) -> str | None:
    """生成任务进度 → 一帧 ``status.message`` 的文本；无话可说时回 ``None``。

    优先任务自带的 ``progress_message``（它通常已含百分比，如「45% 渲染中」），缺失时才用裸
    百分比兜底。两者皆无回 ``None``：调用方据此**不附** ``status.message``，
    而不是塞一个空串冒充进度。
    """
    if isinstance(progress_message, str) and progress_message.strip():
        return progress_message.strip()
    # ``isinstance(True, int)`` 为真：不挡布尔会拼出 "True%" 这种脏值。
    if isinstance(percent, int) and not isinstance(percent, bool):
        return f"{percent}%"
    return None


def timestamp_iso(value: datetime | None) -> str:
    """``datetime`` → A2A ``TaskStatus.timestamp``；非 ``datetime`` 回退当前时刻。

    任务的真实状态时间（``TimestampMixin.updated_at``）优先：用请求时刻会让对端每次都看到
    「刚刚更新」，据它判断新鲜度、超时或去重都会误判。``message/stream`` 的合成 taskId 与
    ``message/send`` 的提交快照无真实对象可依，调用点自行传 ``now_iso()``。

    回退经包门面 ``server.now_iso`` 解析，便于单测 monkeypatch 该门面属性。
    """
    if isinstance(value, datetime):
        return value.isoformat()
    from miles_portal.tenant.a2a import server as server_mod

    return server_mod.now_iso()


def build_a2a_task_status(
    *,
    state: str,
    timestamp: str,
    context_id: str | None = None,
    text: str | None = None,
    percent: object = None,
    message_task_id: str | None = None,
    job_task_id: str | None = None,
) -> dict:
    """A2A ``TaskStatus``：``Task.status`` 与 ``TaskStatusUpdateEvent.status`` 共用一份形状。

    ``text`` 与 ``percent`` 成对描述进度：``text`` 渲染成嵌套消息的文本 part，``percent``
    写进该消息的 ``metadata.percent``。``text`` 为空则**不附** ``status.message`` —— 与其
    塞一个空串冒充「有进度」，不如让对端明确知道本帧没有进展可说。

    ``job_task_id`` 非空时写入 ``metadata.a2aJobTaskId``：``message/stream`` 的 taskId 是
    合成的（流开始时就得定），生成任务 id 只有跑完才知道，故不强行合一，改用该扩展位串起来。
    """
    status: dict = {"state": state, "timestamp": timestamp}
    if text is None:
        return status
    message = build_a2a_agent_message(text=text, context_id=context_id, task_id=message_task_id)
    metadata: dict = {}
    if job_task_id:
        metadata["a2aJobTaskId"] = job_task_id
    if percent is not None:
        metadata["percent"] = percent
    if metadata:
        message["metadata"] = metadata
    status["message"] = message
    return status


def build_a2a_task(
    *,
    task_id: str,
    context_id: str | None,
    state: str,
    timestamp: str,
    artifacts: list[dict] | None = None,
    text: str | None = None,
    percent: object = None,
) -> dict:
    """构造 A2A ``Task``。

    ``contextId`` / ``artifacts`` / ``status.message`` 均为可选：解析不到就省略而非塞空值；
    ``history`` 暂不产出（对端的原始消息本就在请求里）。

    ``text`` / ``percent`` 与 ``build_a2a_status_update`` 同名同义，透传给
    ``build_a2a_task_status`` —— ``status`` 的形状只在那一个函数里维护。
    """
    task: dict = {
        "kind": "task",
        "id": task_id,
        "status": build_a2a_task_status(
            state=state,
            timestamp=timestamp,
            context_id=context_id,
            text=text,
            percent=percent,
            message_task_id=task_id,
        ),
    }
    if context_id:
        task["contextId"] = context_id
    if artifacts:
        task["artifacts"] = artifacts
    return task


def build_a2a_agent_message(*, text: str, context_id: str | None, task_id: str | None = None) -> dict:
    """A2A ``Message``（agent 角色）。

    ``contextId`` 能取到才回显：解析不到就省略该字段，不塞空串冒充一个假的上下文标识
    （``Task.contextId`` 一贯如此，本函数与它对齐）。``taskId`` 仅在该消息属于某个 Task
    时带上（流式帧的嵌套消息带，``message/send`` 的同步回答不带 —— 同步回答不产生任务）。
    """
    message: dict = {
        "kind": "message",
        "role": "agent",
        "messageId": str(uuid4()),
        "parts": [{"kind": "text", "text": text}],
    }
    if context_id:
        message["contextId"] = context_id
    if task_id:
        message["taskId"] = task_id
    return message


def build_a2a_status_update(
    *,
    task_id: str,
    context_id: str | None,
    state: str,
    timestamp: str,
    text: str | None = None,
    final: bool = False,
    job_task_id: str | None = None,
    percent: object = None,
) -> dict:
    """A2A ``TaskStatusUpdateEvent``（``message/stream`` 与 ``tasks/resubscribe`` 的帧载荷）。

    ``final`` 表示「本流结束」，不等于「任务终态」—— 产生异步生成任务时以
    ``working`` + ``final=True`` 收尾，对端再转向 ``tasks/get`` 轮询。

    ``job_task_id`` 非空时写入嵌套消息的 ``metadata.a2aJobTaskId``：``message/stream`` 的
    taskId 是合成的（流开始时就得定），生成任务 id 只有跑完才知道，故不强行合一，改用该扩展位
    把两者串起来。``percent`` 同理写进 ``metadata.percent``（订阅流的进度百分比）。

    ``contextId`` 解析不到就省略（规范标必填，此处有意偏离，见设计 §3.8）。
    """
    status = build_a2a_task_status(
        state=state,
        timestamp=timestamp,
        context_id=context_id,
        text=text,
        percent=percent,
        message_task_id=task_id,
        job_task_id=job_task_id,
    )
    event: dict = {
        "kind": "status-update",
        "taskId": task_id,
        "status": status,
        "final": final,
    }
    if context_id:
        event["contextId"] = context_id
    return event


def artifact_ids_from_job_result(job_result: object) -> list[str]:
    """从生成任务 ``result`` 取产物附件 ID。

    生图是多产物（``attachment_ids``），生视频单个（``attachment_id``）；去重并丢弃空值，
    否则会产出指向 ``None`` 的下载地址。
    """
    if not isinstance(job_result, dict):
        return []
    raw = job_result.get("attachment_ids")
    candidates = list(raw) if isinstance(raw, list) else []
    single = job_result.get("attachment_id")
    if single:
        candidates.append(single)

    ids: list[str] = []
    for item in candidates:
        if isinstance(item, str) and item.strip() and item not in ids:
            ids.append(item)
    return ids


def build_a2a_artifacts(
    *,
    job_result: object,
    agent_id: UUID | str,
    task_id: UUID | str,
    base_url: str,
) -> list[dict]:
    """生成任务产物 → A2A ``Artifact`` 列表。

    ``file.uri`` 指向本平台的开放下载端点（**需 ``X-API-Key``**），而非对象存储签名 URL
    —— 与平台「不以签名链接外泄文件」的既有取向一致。
    """
    if not isinstance(job_result, dict):
        return []
    mime_type = job_result.get("mime_type")
    kind = job_result.get("kind")
    artifacts: list[dict] = []
    for index, attachment_id in enumerate(artifact_ids_from_job_result(job_result)):
        file: dict = {"uri": f"{base_url.rstrip('/')}{a2a_task_artifact_path(agent_id, task_id, attachment_id)}"}
        if isinstance(mime_type, str) and mime_type:
            file["mimeType"] = mime_type
        if isinstance(kind, str) and kind:
            file["name"] = f"{kind}-{index + 1}"
        artifacts.append(
            {
                "artifactId": attachment_id,
                "parts": [{"kind": "file", "file": file}],
            }
        )
    return artifacts


def build_a2a_artifact_update(
    *,
    task_id: str,
    context_id: str | None,
    artifact: dict,
    last_chunk: bool = True,
) -> dict:
    """构造 A2A ``TaskArtifactUpdateEvent``（订阅流里「本次产出的新产物」帧）。

    ``artifact`` 直接取 ``build_a2a_artifacts`` 的单项产出（其元素本就是完整的 ``Artifact``），
    故 ``file.uri`` 的拼法仍只有那一处，这里不再重拼。
    """
    event: dict = {
        "kind": "artifact-update",
        "taskId": task_id,
        "artifact": artifact,
        "lastChunk": last_chunk,
    }
    if context_id:
        event["contextId"] = context_id
    return event


def jsonrpc_result(req_id: object, result: dict) -> dict:
    """JSON-RPC 2.0 成功信封。"""
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def jsonrpc_error(req_id: object, code: int, message: str, data: dict | None = None) -> dict:
    """JSON-RPC 2.0 错误信封；``data`` 非空时附结构化细节（规范允许）。"""
    error: dict = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}


def app_error_envelope(method: str | None, req_id: object, exc: AppError) -> dict:
    """把 ``AppError`` 译成 JSON-RPC 错误信封；A2A 对外面不接受平台信封。

    逐点映射（各 ``_handle_*`` 里的 ``except``）仍是第一道，语义更精确；本函数是
    「handler 漏捕或捕得太宽」时的统一归属，保证对外形状一致。

    ``tasks/*`` 域的 401/403/404 压成 ``TASK_NOT_FOUND``：延续「对端不得获得存在性
    oracle」的不变式。其余域的权限/冲突问题压成 ``INVALID_PARAMS`` / ``INTERNAL_ERROR``，
    对端读不出真实原因 —— 这是已知取舍，由审计的 ``errorType``/``errorStatus`` 补偿。
    """
    status = exc.status_code
    if isinstance(method, str) and method.startswith(_TASKS_METHOD_PREFIX) and status in (401, 403, 404):
        code = TASK_NOT_FOUND
    elif status in (400, 401, 403, 404):
        code = INVALID_PARAMS
    else:
        code = INTERNAL_ERROR
    return jsonrpc_error(req_id, code, exc.message)
