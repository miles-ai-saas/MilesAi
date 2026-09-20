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
    endpoints = [
        urljoin(rpc_base + "/", "message/send"),
        rpc_base,
    ]
    last_err: str | None = None
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for url in endpoints:
            try:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code >= 400:
                    last_err = f"HTTP {resp.status_code}"
                    continue
                data = resp.json()
                text = _extract_text_from_response(data)
                if text:
                    return text
            except httpx.RequestError as e:
                last_err = str(e)
            except ValueError:
                last_err = "响应非 JSON"

    raise BadRequestError(f"调用外部 A2A Agent「{peer.name}」失败" + (f"：{last_err}" if last_err else ""))
