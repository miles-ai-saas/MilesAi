"""A2A ``message/send`` / ``tasks/cancel`` HTTP 调用。"""

from __future__ import annotations

import uuid
from urllib.parse import urljoin

import httpx

from miles_common.exceptions import BadRequestError
from miles_portal.tenant.a2a.client.auth import JSONRPC_HEADERS, build_auth_headers
from miles_portal.tenant.a2a.client.parse import _extract_text_from_response, _jsonrpc_error
from miles_portal.tenant.a2a.client.task import _looks_like_task, _resolve_agent_task
from miles_portal.tenant.a2a.client.url import _pick_rpc_url
from miles_portal.tenant.a2a.models import A2aPeer


async def invoke_a2a_peer(peer: A2aPeer, task: str) -> str:
    """向已同步 Card 的外部 Agent 发送任务（JSON-RPC message/send 或 HTTP 降级）。"""
    from miles_portal.tenant.a2a import client as client_mod

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
    async with client_mod.httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
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


async def cancel_a2a_peer_task(peer: A2aPeer, task_id: str) -> None:
    """请对端取消一个异步任务。成功返回；被拒或不可达抛 ``BadRequestError``。

    **本批没有任何调用方**：``invoke_a2a_peer`` 的轮询超时不会调用它。超时只表达「我不想
    再等了」，不等于「放弃这个任务」——而对端任务的产物落在对端租户、属于对端用户，贸然
    取消会把一个再过几秒就完成的任务连同产物一起销毁。这个函数是为「上游将来出现明确的
    放弃语义」（如用户显式中止）预留的能力。
    """
    from miles_portal.tenant.a2a import client as client_mod

    if peer.status.value != "active" or not (peer.agent_card_json or {}):
        raise BadRequestError(f"外部 Agent「{peer.name}」尚未同步 Agent Card 或未连通")
    rpc_base = _pick_rpc_url(peer)
    if not rpc_base:
        raise BadRequestError(f"外部 Agent「{peer.name}」的 Card 未声明可调用的 JSON-RPC 端点")

    payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tasks/cancel", "params": {"id": task_id}}
    headers = {**JSONRPC_HEADERS, **build_auth_headers(peer.auth_config)}
    endpoints = [urljoin(rpc_base + "/", "tasks/cancel"), rpc_base]
    last_err: str | None = None
    async with client_mod.httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for url in endpoints:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.RequestError as exc:
                last_err = str(exc)
                continue
            if resp.status_code >= 400:
                last_err = f"HTTP {resp.status_code}"
                continue
            try:
                data = resp.json()
            except ValueError:
                last_err = "响应非 JSON"
                continue
            err = _jsonrpc_error(data)
            if err is not None:
                # 对端已按 JSON-RPC 应答，说明端点形态已匹配：不再试下一个。
                raise BadRequestError(f"取消外部 A2A Agent「{peer.name}」的任务失败：对端返回错误 {err[0]} {err[1]}")
            return
    raise BadRequestError(f"取消外部 A2A Agent「{peer.name}」的任务失败" + (f"：{last_err}" if last_err else ""))
