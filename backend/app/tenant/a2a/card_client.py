"""
拉取 A2A Agent Card（``/.well-known/agent-card.json``）。

流程
----
``A2aPeerService.sync`` → ``resolve_agent_card_url`` → ``fetch_agent_card``
→ 写入 ``A2aPeer.agent_card_json``，供 ``invoke_a2a_peer`` 解析 RPC 端点。

``supportedInterfaces`` / ``base_url`` 决定 ``client._pick_rpc_url`` 能否真实 HTTP 调用。
"""

from urllib.parse import urljoin, urlparse

import httpx

from app.common.exceptions import BadRequestError

WELL_KNOWN_CARD = "/.well-known/agent-card.json"


def resolve_agent_card_url(base_or_card_url: str) -> str:
    raw = (base_or_card_url or "").strip()
    if not raw:
        raise BadRequestError("请填写外部 Agent 根地址或 Agent Card URL")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if not parsed.netloc:
        raise BadRequestError("无效的 URL")
    path = parsed.path.rstrip("/")
    if path.endswith("agent-card.json"):
        return raw.split("?")[0]
    if "/.well-known/" in path:
        return raw.split("?")[0]
    base = f"{parsed.scheme}://{parsed.netloc}"
    return urljoin(base + "/", WELL_KNOWN_CARD.lstrip("/"))


def card_display_name(card: dict) -> str | None:
    """从 Card JSON 提取展示名称。"""
    for key in ("name", "agentName", "title"):
        val = card.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:256]
    return None


def count_card_skills(card: dict) -> int:
    """统计 Card 中 skills 数组长度。"""
    skills = card.get("skills")
    if isinstance(skills, list):
        return len(skills)
    return 0


async def fetch_agent_card(base_or_card_url: str) -> tuple[dict, str]:
    """HTTP GET Agent Card，返回 (card_json, 最终 card_url)。"""
    card_url = resolve_agent_card_url(base_or_card_url)
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(
                card_url,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise BadRequestError(f"拉取 Agent Card 失败 HTTP {e.response.status_code}: {card_url}") from e
    except httpx.RequestError as e:
        raise BadRequestError(f"无法连接外部 Agent: {e}") from e
    except ValueError as e:
        raise BadRequestError(f"Agent Card 响应不是合法 JSON: {card_url}") from e

    if not isinstance(data, dict):
        raise BadRequestError("Agent Card 必须为 JSON 对象")
    return data, card_url
