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

from miles_common.exceptions import BadRequestError
from miles_portal.tenant.a2a.models import A2aPeer

JSONRPC_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def _base_from_card_url(card_url: str) -> str:
    """从 Agent Card URL 提取 scheme://host。"""
    parsed = urlparse(card_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _pick_rpc_url(peer: A2aPeer) -> str | None:
    """从 Card supportedInterfaces 或 base_url 解析 JSON-RPC 端点。"""
    card = peer.agent_card_json or {}
    interfaces = card.get("supportedInterfaces") or card.get("supported_interfaces")
    if isinstance(interfaces, list):
        for item in interfaces:
            if not isinstance(item, dict):
                continue
            binding = str(item.get("protocolBinding") or item.get("url") or "")
            if binding.startswith("http"):
                return binding.rstrip("/")
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
                "parts": [{"type": "text", "text": task}],
            }
        },
    }
    endpoints = [
        urljoin(rpc_base + "/", "message/send"),
        rpc_base,
    ]
    last_err: str | None = None
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for url in endpoints:
            try:
                resp = await client.post(url, json=payload, headers=JSONRPC_HEADERS)
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
