"""A2A Task 状态判定、渲染与 ``tasks/get`` 轮询。"""

from __future__ import annotations

import asyncio
import time
import uuid

import httpx

from miles_portal.tenant.a2a.client.parse import _first_part_text, _jsonrpc_error

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

#: 轮询间隔与总上限。不设为配置项：60s 与 ``invoke_a2a_peer`` 的 httpx 单请求超时同量级，
#: 且单次调用上限直接等于「用户为这个外部 peer 多等多久」，按 peer 调参是另一个量级的运营面。
#: 单测经 ``client`` 包门面 ``monkeypatch.setattr(client_mod, "TASK_POLL_*", …)``；本模块经门面读取。
TASK_POLL_INTERVAL_SECONDS = 2.0
TASK_POLL_TIMEOUT_SECONDS = 60.0


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
        uri = file_obj.get("uri") if file_obj is not None else None
        if not (isinstance(uri, str) and uri):
            # ``file`` 缺失、或存在却给不出 ``uri``，两者都渲染不出下载地址：此前只处理
            # 前者，后者会渲染成字面量 ``None``，既不能读也误导上层。
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


def _tasks_get_payload(task_id: str) -> dict:
    """``tasks/get`` 的 JSON-RPC 请求体。"""
    return {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tasks/get", "params": {"id": task_id}}


async def _resolve_agent_task(client: httpx.AsyncClient, url: str, task: dict, headers: dict[str, str]) -> str:
    """把一个 ``Task`` 响应变成回答：已是停止轮询态就直接渲染，否则轮询到停止轮询态。

    **本函数不得向上抛 ``httpx.RequestError`` / ``ValueError``**：调用它的位置在
    ``invoke_a2a_peer`` 的 endpoint 循环内，那层的 ``except`` 会把这里的结果丢掉并对第二个
    endpoint 重跑一遍（最坏 120s 且用户拿不到任何结论）。

    ``TASK_POLL_TIMEOUT_SECONDS`` 是**整段轮询**的上限：它既 cap 睡眠，也 cap 单次
    ``tasks/get``（见下），故一轮不会叠上 httpx 自己的 60s。

    轮询间隔/超时经 ``client`` 包门面读取，便于单测 monkeypatch。
    """
    from miles_portal.tenant.a2a import client as client_mod

    # 先判停止轮询态再看 ``id``：终态/中断态本就不需要继续查询，缺 ``id`` 也不该被
    # 报「无法继续查询」——那是一个从未发生的需求。
    if _task_state(task) in STOP_POLLING_TASK_STATES:
        return _render_agent_task(task)
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id:
        return _render_agent_task(task, note="对端未给出任务 ID，无法继续查询")

    poll_timeout = client_mod.TASK_POLL_TIMEOUT_SECONDS
    poll_interval = client_mod.TASK_POLL_INTERVAL_SECONDS
    deadline = time.monotonic() + poll_timeout
    latest = task
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        # 先睡再查：首响应已是「刚提交」，立刻重查只会打一个空转请求。
        await asyncio.sleep(min(poll_interval, remaining))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            # 预算同时约束这一次 ``tasks/get``：只 cap 睡眠的话，请求自身还能再吃掉
            # httpx 的 60s，一轮最坏 ~120s，文档承诺的 60s 上限就是空话。
            # 选 ``asyncio.timeout``：它把「预算耗尽」变成内置 ``TimeoutError``，与外层
            # ``httpx.RequestError``（真实网络故障）天然分开，故预算用完仍走「已等待」快照，
            # 不会误报成「网络异常」。
            async with asyncio.timeout(remaining):
                resp = await client.post(url, json=_tasks_get_payload(task_id), headers=headers)
                if resp.status_code >= 400:
                    return _render_agent_task(latest, note=f"继续查询失败（HTTP {resp.status_code}）")
                data = resp.json()
        except TimeoutError:
            # 静默可接受：预算耗尽是预期控制流（非故障），落到循环外走「已等待」快照。
            # 本 arm 只负责 ``asyncio.timeout`` 的预算耗尽。httpx 自己的超时不会打到这里：
            # ``httpx.TimeoutException`` 是 ``RequestError`` 的子类，与内置 ``TimeoutError``
            # 无继承关系（故它照旧落到下面的 ``RequestError`` arm，被如实报成网络故障）。
            break
        except httpx.RequestError:
            return _render_agent_task(latest, note="继续查询失败（网络异常）")
        except ValueError:
            # 解析失败不是网络故障：代理回 200 + HTML 就落在这里。
            return _render_agent_task(latest, note="继续查询失败（响应非 JSON）")
        err = _jsonrpc_error(data)
        if err is not None:
            # 只如实转述对端给出的码与消息，不推断成因：任意 ``error`` 都回退，``-32601``
            # 只是「对端不支持 tasks/get」最典型的那一种，不是唯一可能。
            return _render_agent_task(latest, note=f"继续查询失败（对端返回错误 {err[0]} {err[1]}）")
        if not _looks_like_task(data):
            # 形状不认识不是失败信号：保留最后一次已知状态，继续等。
            continue
        latest = data["result"]
        if _task_state(latest) in STOP_POLLING_TASK_STATES:
            return _render_agent_task(latest)
    return _render_agent_task(latest, note=f"已等待 {int(poll_timeout)} 秒")
