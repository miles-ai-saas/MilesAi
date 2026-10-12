"""A2A Agent Card 组装与路径（纯逻辑）。"""

from __future__ import annotations

from uuid import UUID

from miles_common.constants import AGENT_API_KEY_HEADER
from miles_portal.tenant.a2a.server.constants import (
    A2A_PROTOCOL_BINDING,
    A2A_PROTOCOL_VERSION,
    A2A_PUBLISH_FLAG,
    A2A_SECURITY_SCHEME,
)


def is_publish_enabled(config: dict | None) -> bool:
    """``config.a2a_publish`` 是否显式为布尔 ``True``。

    只认布尔值：字符串 ``"true"`` / ``"1"`` 一律视为未开启 —— 该键由表单写入布尔，
    若在此兼容字符串，则「配置里写了但没生效」这类问题会被静默吞掉。
    """
    if not isinstance(config, dict):
        return False
    return config.get(A2A_PUBLISH_FLAG) is True


def agent_card_rpc_path(agent_id: UUID | str) -> str:
    """对外 JSON-RPC 端点路径（Card ``url`` / ``additionalInterfaces[].url``）。"""
    return f"/api/v1/open/a2a/agents/{agent_id}"


def agent_card_well_known_path(agent_id: UUID | str) -> str:
    """对外 Agent Card 路径。"""
    return f"{agent_card_rpc_path(agent_id)}/.well-known/agent-card.json"


def a2a_task_artifact_path(agent_id: UUID | str, task_id: UUID | str, attachment_id: UUID | str) -> str:
    """任务产物下载路径（``Task.artifacts[].parts[].file.uri`` 的 path 部分）。

    与 Card 同理按智能体寻址，并额外绑定任务与附件 —— 授权范围精确到「该智能体该任务的
    这个产物」，而非「本租户任意附件」。
    """
    return f"{agent_card_rpc_path(agent_id)}/tasks/{task_id}/artifacts/{attachment_id}"


def build_agent_card(
    *,
    agent_id: UUID | str,
    name: str,
    description: str | None,
    base_url: str,
    skills: list[dict] | None = None,
) -> dict:
    """构造 A2A Agent Card。

    ``base_url`` 取自请求的 scheme://host（多环境无需新增配置项）。``skills`` 为空时以
    智能体自身作为一个 skill —— A2A 的 ``skills`` 是能力声明，空数组会让对端认为该
    Agent 无任何能力。
    """
    base = base_url.rstrip("/")
    rpc_url = f"{base}{agent_card_rpc_path(agent_id)}"
    card_skills = skills or [
        {
            "id": str(agent_id),
            "name": name,
            "description": description or "",
            "tags": [],
        }
    ]
    return {
        "name": name,
        "description": description or "",
        "url": rpc_url,
        "version": "1.0.0",
        "protocolVersion": A2A_PROTOCOL_VERSION,
        "preferredTransport": A2A_PROTOCOL_BINDING,
        "capabilities": {
            "streaming": True,
            "pushNotifications": True,
            "stateTransitionHistory": False,
        },
        # 入站已支持 text + image file parts；输出仍以文本（产物下载另走 artifacts URI）。
        "defaultInputModes": ["text", "image"],
        "defaultOutputModes": ["text"],
        "skills": card_skills,
        # 0.3 的接口数组：``additionalInterfaces[{url, transport}]``（v1.0 改名为
        # ``supportedInterfaces[{url, protocolBinding, protocolVersion}]``）。每项不带
        # ``protocolVersion`` —— 版本由 Card 顶层字段统一声明，接口项只描述「哪个 URL 说哪个传输」。
        # 主 url 的接口也要在这里出现（v0.3 §5.6.4 的完整性要求）。
        "additionalInterfaces": [
            {
                "url": rpc_url,
                "transport": A2A_PROTOCOL_BINDING,
            }
        ],
        # 调用端点（非 Card 本身）须带该智能体的 API Key；声明后标准 A2A 客户端才能
        # 从 Card 发现鉴权要求，否则对端只会在 401 处才知道要凭证。
        "securitySchemes": {
            A2A_SECURITY_SCHEME: {
                "type": "apiKey",
                "in": "header",
                "name": AGENT_API_KEY_HEADER,
                "description": "该智能体的 API Key，在智能体详情中创建",
            }
        },
        "security": [{A2A_SECURITY_SCHEME: []}],
    }
