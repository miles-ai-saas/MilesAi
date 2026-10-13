"""从 Agent Card 解析 JSON-RPC 端点。"""

from __future__ import annotations

from urllib.parse import urlparse

from miles_portal.tenant.a2a.models import A2aPeer


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
