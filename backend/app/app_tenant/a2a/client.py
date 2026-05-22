"""A2A 协议最小 Client：向外部 Agent 发送任务消息。"""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.app_tenant.a2a.models import A2aPeer
from app.common.exceptions import BadRequestError

JSONRPC_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def _base_from_card_url(card_url: str) -> str:
    parsed = urlparse(card_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _pick_rpc_url(peer: A2aPeer) -> str | None:
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


def _extract_text_from_response(data: Any) -> str:
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
        for key in ("text", "answer", "content", "message"):
            val = result.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        msg = result.get("message")
        if isinstance(msg, dict):
            for key in ("text", "content", "parts"):
                val = msg.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
                if isinstance(val, list) and val:
                    first = val[0]
                    if isinstance(first, dict) and first.get("text"):
                        return str(first["text"]).strip()
        artifacts = result.get("artifacts")
        if isinstance(artifacts, list) and artifacts:
            art = artifacts[0]
            if isinstance(art, dict):
                parts = art.get("parts")
                if isinstance(parts, list) and parts:
                    p0 = parts[0]
                    if isinstance(p0, dict) and p0.get("text"):
                        return str(p0["text"]).strip()
    return str(result)[:4000]


async def invoke_a2a_peer(peer: A2aPeer, task: str) -> str:
    """向已同步 Card 的外部 Agent 发送任务（JSON-RPC message/send 或 HTTP 降级）。"""
    if peer.status.value != "active" or not (peer.agent_card_json or {}):
        raise BadRequestError(f"外部 Agent「{peer.name}」尚未同步 Agent Card 或未连通")

    rpc_base = _pick_rpc_url(peer)
    if not rpc_base:
        name = peer.card_display_name or peer.name
        return (
            f"[A2A] 已向外部智能体「{name}」提交任务（Card 未声明 HTTP 接口，仅记录任务预览）：\n"
            f"{task[:800]}"
        )

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

    raise BadRequestError(
        f"调用外部 A2A Agent「{peer.name}」失败"
        + (f"：{last_err}" if last_err else "")
    )
