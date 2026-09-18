"""A2A Server：把本平台智能体对外暴露为 Agent Card 与 JSON-RPC 端点。

与 ``card_client.py``（拉远端 Card）方向相反：本模块产 Card、解析入站 ``message/send``。

多租户寻址
----------
平台多租户共用域名，根路径 ``/.well-known/agent-card.json`` 无法区分租户，故 Card 按
智能体寻址：``/api/v1/open/a2a/agents/{agent_id}/.well-known/agent-card.json``；调用端点
为该路径去掉 ``.well-known`` 后缀（``supportedInterfaces[].url`` 声明的正是它）。根路径
仅在「全平台唯一发布」时提供 302 别名，见 ``services/server.resolve_default_published_agent_id``。

本模块为纯函数（无 ORM / 无 DB），可被 API 声明层安全 import。
"""

from __future__ import annotations

from uuid import UUID

from miles_common.constants import AGENT_API_KEY_HEADER
from miles_common.exceptions import BadRequestError

#: ``agent.config`` 中标记「对外暴露为 A2A Server」的键。
A2A_PUBLISH_FLAG = "a2a_publish"

#: Agent Card 声明的协议版本与传输绑定。
A2A_PROTOCOL_VERSION = "1.0"
A2A_PROTOCOL_BINDING = "JSONRPC"

#: ``securitySchemes`` / ``security`` 中引用该方案的键名。
A2A_SECURITY_SCHEME = "apiKey"

#: JSON-RPC 2.0 错误码（A2A 沿用）。
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def is_publish_enabled(config: dict | None) -> bool:
    """``config.a2a_publish`` 是否显式为布尔 ``True``。

    只认布尔值：字符串 ``"true"`` / ``"1"`` 一律视为未开启 —— 该键由表单写入布尔，
    若在此兼容字符串，则「配置里写了但没生效」这类问题会被静默吞掉。
    """
    if not isinstance(config, dict):
        return False
    return config.get(A2A_PUBLISH_FLAG) is True


def agent_card_rpc_path(agent_id: UUID | str) -> str:
    """对外 JSON-RPC 端点路径（Card ``url`` / ``supportedInterfaces[].url``）。"""
    return f"/api/v1/open/a2a/agents/{agent_id}"


def agent_card_well_known_path(agent_id: UUID | str) -> str:
    """对外 Agent Card 路径。"""
    return f"{agent_card_rpc_path(agent_id)}/.well-known/agent-card.json"


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
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": card_skills,
        "supportedInterfaces": [
            {
                "url": rpc_url,
                "protocolBinding": A2A_PROTOCOL_BINDING,
                "protocolVersion": A2A_PROTOCOL_VERSION,
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


def extract_message_text(params: dict) -> str:
    """取 A2A ``message/send`` 的 ``params.message.parts`` 文本，多段以换行拼接。

    无任何非空文本段抛 ``BadRequestError``：静默返回空串会让本平台以空 query 空转一轮
    对话，且对端收到的是「谜之回答」而非参数错误。
    """
    message = params.get("message")
    if not isinstance(message, dict):
        raise BadRequestError("message/send 缺少 message 参数")
    parts = message.get("parts")
    if not isinstance(parts, list):
        raise BadRequestError("message/send 的 message.parts 必须是数组")

    texts: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    if not texts:
        raise BadRequestError("message/send 的 parts 中没有文本内容")
    return "\n".join(texts)


def jsonrpc_result(req_id: object, result: dict) -> dict:
    """JSON-RPC 2.0 成功信封。"""
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def jsonrpc_error(req_id: object, code: int, message: str) -> dict:
    """JSON-RPC 2.0 错误信封。"""
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
