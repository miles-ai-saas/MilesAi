"""
A2A 协议最小 HTTP Client（JSON-RPC 2.0）。

调用链
------
``tenant.a2a.invoke.execute_a2a_calls`` → ``invoke_a2a_peer``
→ 从 ``A2aPeer.agent_card_json`` 解析 RPC URL → ``message/send``

前置条件
--------
Peer ``status=active`` 且已同步 Agent Card；否则 ``BadRequestError`` 或返回任务预览占位文本。

响应解析
--------
``_extract_text_from_response`` 兼容多种 JSON-RPC result 形状（text/artifacts/parts 等）。
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from miles_common.constants import AGENT_API_KEY_HEADER
from miles_common.exceptions import BadRequestError
from miles_portal.tenant.a2a.models import A2aPeer

JSONRPC_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def build_auth_headers(auth_config: dict | None) -> dict[str, str]:
    """``auth_config`` → 出站请求头（无有效配置时返回空字典）。

    约定（可叠加）：
    - ``{"headers": {"X-Foo": "bar"}}`` 任意头透传（对接自定义网关）
    - ``{"api_key": "..."}`` / ``{"x_api_key": "..."}`` → ``X-API-Key``（本平台发布
      A2A Server 的调用凭证）
    - ``{"bearer_token": "..."}`` → ``Authorization: Bearer ...``

    非法值（非字符串 / 空白 / 非字典 headers）逐项跳过而非整单失败：单项脏数据不应
    让整条 Peer 调用失去鉴权头，但也绝不把非法值拼进头里。
    """
    if not isinstance(auth_config, dict):
        return {}
    headers: dict[str, str] = {}

    raw_headers = auth_config.get("headers")
    if isinstance(raw_headers, dict):
        headers.update({str(k): str(v) for k, v in raw_headers.items() if isinstance(v, str)})

    for key in ("api_key", "x_api_key"):
        value = auth_config.get(key)
        if isinstance(value, str) and value.strip():
            headers[AGENT_API_KEY_HEADER] = value.strip()
            break

    bearer = auth_config.get("bearer_token")
    if isinstance(bearer, str) and bearer.strip():
        headers["Authorization"] = f"Bearer {bearer.strip()}"

    return headers


def _base_from_card_url(card_url: str) -> str:
    """从 Agent Card URL 提取 scheme://host。"""
    parsed = urlparse(card_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _pick_rpc_url(peer: A2aPeer) -> str | None:
    """从 Card 的接口数组或 ``base_url`` 解析 JSON-RPC 端点。

    两种线格式都要认：0.3 的对端发 ``additionalInterfaces[{url, transport}]``，v1.0 的对端发
    ``supportedInterfaces[{url, protocolBinding, protocolVersion}]``。数组里 ``url`` 才是端点，
    ``transport`` / ``protocolBinding`` 只是传输标签（如 ``JSONRPC``）。此前先读传输标签，其永
    不以 ``http`` 开头，以致平台自己产出的 Card 的 ``url`` 被忽略、退回 ``base_url``（通常只是
    host 根），反向把本平台发布的智能体登记为 Peer 时必然调不通。故以 ``url`` 为准；仅当传输
    标签本身写成 URL（非标准写法）时才兜底采用。
    """
    card = peer.agent_card_json or {}
    for field in ("additionalInterfaces", "additional_interfaces", "supportedInterfaces", "supported_interfaces"):
        interfaces = card.get(field)
        if not isinstance(interfaces, list):
            continue
        for item in interfaces:
            if not isinstance(item, dict):
                continue
            for key in ("url", "transport", "protocolBinding"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate.startswith("http"):
                    return candidate.rstrip("/")
    base = peer.base_url or _base_from_card_url(peer.agent_card_url)
    return base.rstrip("/") if base else None


_RESULT_TEXT_KEYS = ("text", "answer", "content", "message")
_MESSAGE_TEXT_KEYS = ("text", "content", "parts")


def _first_part_text(value: Any) -> str | None:
    """``parts`` 形态（``[{"text": ...}]``）取首项文本；非该形态返回 None。"""
    if not isinstance(value, list) or not value:
        return None
    first = value[0]
    if isinstance(first, dict) and first.get("text"):
        return str(first["text"]).strip()
    return None


def _text_from_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """按 ``keys`` 顺序取首个非空字符串（全空白视为未命中）。"""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _text_or_parts_from_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """按 ``keys`` 顺序取非空字符串；该项为 ``parts`` 形态时取首项文本。"""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        parts_text = _first_part_text(value)
        if parts_text:
            return parts_text
    return None


def _text_from_result_payload(result: dict[str, Any]) -> str | None:
    """``result`` 字典 → 可读文本：常见文本键 → ``message`` 下钻 → ``artifacts`` 下钻。"""
    text = _text_from_keys(result, _RESULT_TEXT_KEYS)
    if text:
        return text
    message = result.get("message")
    if isinstance(message, dict):
        text = _text_or_parts_from_keys(message, _MESSAGE_TEXT_KEYS)
        if text:
            return text
    artifacts = result.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        artifact = artifacts[0]
        if isinstance(artifact, dict):
            text = _first_part_text(artifact.get("parts"))
            if text:
                return text
    return None


def _jsonrpc_error(data: object) -> tuple[object, str] | None:
    """顶层 ``error`` → ``(code, message)``；无 ``error`` 返回 ``None``。

    JSON-RPC 里 ``error`` 与 ``result`` 互斥，故本函数是「本次调用成功还是失败」的判据。
    此前这个判断被交给 ``_extract_text_from_response``（它刻意让 error 优先于 result 并
    把消息榨成文本，见其特征化测试），结果是协议级失败被当成对端的「回答」写进主模型素材。
    """
    if not isinstance(data, dict) or "error" not in data:
        return None
    err = data["error"]
    if isinstance(err, dict):
        return err.get("code"), str(err.get("message") or err)
    return None, str(err)


#: 终态：任务不再推进，且已有最终结果。
TERMINAL_TASK_STATES = frozenset({"completed", "failed", "canceled", "rejected"})
#: 中断态：规范里 ``input-required`` / ``auth-required`` 同样「不再自行推进」——对端在等
#: 我们补输入或凭证。继续轮询只会白等，应停止并如实回报（尤其是 ``input-required``：
#: 对端的提问通常就写在 ``status.message`` 里，正是我们该带回给上层的东西）。
INTERRUPTED_TASK_STATES = frozenset({"input-required", "auth-required"})
#: 停止轮询的状态集。
STOP_POLLING_TASK_STATES = TERMINAL_TASK_STATES | INTERRUPTED_TASK_STATES

#: 任务状态 → 回答首行。未列出的（含缺失）按「仍在进行 / 状态未知」处理。
_TASK_HEADLINES = {
    "completed": "外部任务已完成",
    "failed": "外部任务失败",
    "canceled": "外部任务已取消",
    "rejected": "外部任务被拒绝",
    "input-required": "外部任务需要补充输入",
    "auth-required": "外部任务需要鉴权",
}


def _task_state(task: dict) -> str | None:
    """``Task.status.state``；缺失或非字符串返回 ``None``。"""
    status = task.get("status")
    if not isinstance(status, dict):
        return None
    state = status.get("state")
    return state if isinstance(state, str) else None


def _looks_like_task(data: object) -> bool:
    """JSON-RPC 响应是否是一个 ``Task``。

    用 ``status.state`` 判定而非 ``kind``：0.3 规范里 ``Task.kind`` 是必填，但本模块一直
    兼容不带 ``kind`` 的松散形状，判据不能建立在它上面。
    """
    if not isinstance(data, dict):
        return False
    result = data.get("result")
    return isinstance(result, dict) and _task_state(result) is not None


def _artifact_lines(artifacts: object) -> list[str]:
    """``Task.artifacts`` → 逐条可读引用（只给地址，绝不下载内容）。"""
    if not isinstance(artifacts, list):
        return []
    lines: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        label = str(artifact.get("artifactId") or "产物")
        parts = artifact.get("parts")
        file_obj: dict | None = None
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict) and isinstance(part.get("file"), dict):
                    file_obj = part["file"]
                    break
        if file_obj is None:
            lines.append(f"- {label}（无下载地址）")
            continue
        uri = file_obj.get("uri")
        if not (isinstance(uri, str) and uri):
            # ``file`` 存在但没有 ``uri`` 同样给不出下载地址：此前会渲染成字面量
            # ``None``，既不能读也误导上层。
            lines.append(f"- {label}（无下载地址）")
            continue
        name = file_obj.get("name") or label
        mime = file_obj.get("mimeType")
        suffix = f"（{mime}）" if isinstance(mime, str) and mime else ""
        lines.append(f"- {name}{suffix}：{uri}")
    return lines


def _render_agent_task(task: dict, *, note: str | None = None) -> str:
    """``Task`` → 给上层（与主模型）读的多行文本。

    不带 peer 名：调用方 ``invoke.py`` 已用 ``【外部 A2A · {name}】`` 包过，重复无益。
    """
    state = _task_state(task) or "unknown"
    if state in _TASK_HEADLINES:
        lines = [_TASK_HEADLINES[state]]
    elif state == "unknown":
        lines = ["外部任务状态未知（状态：unknown）"]
    else:
        lines = [f"外部任务仍在进行（状态：{state}）"]
    status = task.get("status")
    message = status.get("message") if isinstance(status, dict) else None
    progress = _first_part_text(message.get("parts")) if isinstance(message, dict) else None
    if progress:
        lines.append(f"进展：{progress}")
    artifacts = task.get("artifacts")
    artifact_lines = _artifact_lines(artifacts)
    if artifact_lines:
        lines.append(f"产物（{len(artifact_lines)} 个）：")
        lines.extend(artifact_lines)
    the_id = task.get("id")
    if isinstance(the_id, str) and the_id:
        lines.append(f"任务 ID：{the_id}")
    if note:
        lines.append(note)
    return "\n".join(lines)


#: 轮询间隔与总上限。不设为配置项：60s 与 ``invoke_a2a_peer`` 的 httpx 单请求超时同量级，
#: 且单次调用上限直接等于「用户为这个外部 peer 多等多久」，按 peer 调参是另一个量级的运营面。
TASK_POLL_INTERVAL_SECONDS = 2.0
TASK_POLL_TIMEOUT_SECONDS = 60.0


def _tasks_get_payload(task_id: str) -> dict:
    """``tasks/get`` 的 JSON-RPC 请求体。"""
    return {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tasks/get", "params": {"id": task_id}}


async def _resolve_agent_task(client: httpx.AsyncClient, url: str, task: dict, headers: dict[str, str]) -> str:
    """把一个 ``Task`` 响应变成回答：已是停止轮询态就直接渲染，否则轮询到停止轮询态。

    **本函数不得向上抛 ``httpx.RequestError`` / ``ValueError``**：调用它的位置在
    ``invoke_a2a_peer`` 的 endpoint 循环内，那层的 ``except`` 会把这里的结果丢掉并对第二个
    endpoint 重跑一遍（最坏 120s 且用户拿不到任何结论）。
    """
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id:
        return _render_agent_task(task, note="对端未给出任务 ID，无法继续查询")
    if _task_state(task) in STOP_POLLING_TASK_STATES:
        return _render_agent_task(task)

    deadline = time.monotonic() + TASK_POLL_TIMEOUT_SECONDS
    latest = task
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        # 先睡再查：首响应已是「刚提交」，立刻重查只会打一个空转请求。
        await asyncio.sleep(min(TASK_POLL_INTERVAL_SECONDS, remaining))
        try:
            resp = await client.post(url, json=_tasks_get_payload(task_id), headers=headers)
            if resp.status_code >= 400:
                return _render_agent_task(latest, note=f"继续查询失败（HTTP {resp.status_code}）")
            data = resp.json()
        except (httpx.RequestError, ValueError):
            return _render_agent_task(latest, note="继续查询失败（网络异常）")
        err = _jsonrpc_error(data)
        if err is not None:
            return _render_agent_task(latest, note=f"对端不支持继续查询（{err[0]} {err[1]}）")
        if not _looks_like_task(data):
            # 形状不认识不是失败信号：保留最后一次已知状态，继续等。
            continue
        latest = data["result"]
        if _task_state(latest) in STOP_POLLING_TASK_STATES:
            return _render_agent_task(latest)
    return _render_agent_task(latest, note=f"已等待 {int(TASK_POLL_TIMEOUT_SECONDS)} 秒")


def _extract_text_from_response(data: Any) -> str:
    """从 JSON-RPC / HTTP 响应中提取可读文本。"""
    if isinstance(data, str):
        return data.strip()
    if not isinstance(data, dict):
        return str(data)
    if "error" in data:
        err = data["error"]
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err)
    result = data.get("result", data)
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        text = _text_from_result_payload(result)
        if text:
            return text
    return str(result)[:4000]


async def invoke_a2a_peer(peer: A2aPeer, task: str) -> str:
    """向已同步 Card 的外部 Agent 发送任务（JSON-RPC message/send 或 HTTP 降级）。"""
    if peer.status.value != "active" or not (peer.agent_card_json or {}):
        raise BadRequestError(f"外部 Agent「{peer.name}」尚未同步 Agent Card 或未连通")

    rpc_base = _pick_rpc_url(peer)
    if not rpc_base:
        name = peer.card_display_name or peer.name
        return f"[A2A] 已向外部智能体「{name}」提交任务（Card 未声明 HTTP 接口，仅记录任务预览）：\n{task[:800]}"

    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": task}],
            }
        },
    }
    headers = {**JSONRPC_HEADERS, **build_auth_headers(peer.auth_config)}
    message_endpoints = [
        urljoin(rpc_base + "/", "message/send"),
        rpc_base,
    ]
    #: 与 message_endpoints 逐位对称：探到哪一种部署形态，tasks/get 就打对应的那一个
    #: （否则每轮轮询都要先打一个必然 404 的请求，对端限流下等于白烧配额）。
    tasks_get_endpoints = [
        urljoin(rpc_base + "/", "tasks/get"),
        rpc_base,
    ]
    last_err: str | None = None
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for index, url in enumerate(message_endpoints):
            try:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code >= 400:
                    last_err = f"HTTP {resp.status_code}"
                    continue
                data = resp.json()
                # 顺序固定 error → task → text（三者互斥）。判断「成功还是失败」是本层的
                # 职责，不交给榨文本函数：否则对端错误会被当成回答交上去。
                err = _jsonrpc_error(data)
                if err is not None:
                    # 对端已按 JSON-RPC 应答，说明 endpoint 形态已匹配：不再探测下一个，
                    # 直接抛。HTTP ≥ 400 仍走上面的 ``continue`` —— 那可能只是路径不对。
                    raise BadRequestError(f"调用外部 A2A Agent「{peer.name}」失败：对端返回错误 {err[0]} {err[1]}")
                if _looks_like_task(data):
                    return await _resolve_agent_task(client, tasks_get_endpoints[index], data["result"], headers)
                text = _extract_text_from_response(data)
                if text:
                    return text
            except httpx.RequestError as e:
                last_err = str(e)
            except ValueError:
                last_err = "响应非 JSON"

    raise BadRequestError(f"调用外部 A2A Agent「{peer.name}」失败" + (f"：{last_err}" if last_err else ""))
