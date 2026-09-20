"""A2A Server：把本平台智能体对外暴露为 Agent Card 与 JSON-RPC 端点。

与 ``card_client.py``（拉远端 Card）方向相反：本模块产 Card、解析入站 ``message/send``。

多租户寻址
----------
平台多租户共用域名，根路径 ``/.well-known/agent-card.json`` 无法区分租户，故 Card 按
智能体寻址：``/api/v1/open/a2a/agents/{agent_id}/.well-known/agent-card.json``；调用端点
为该路径去掉 ``.well-known`` 后缀（``additionalInterfaces[].url`` 声明的正是它）。根路径
仅在「全平台唯一发布」时提供 302 别名，见 ``services/server.resolve_default_published_agent_id``。

本模块为纯函数（无 ORM / 无 DB），可被 API 声明层安全 import。
"""

from __future__ import annotations

from uuid import UUID, uuid4

from miles_common.constants import AGENT_API_KEY_HEADER
from miles_common.exceptions import BadRequestError
from miles_common.schemas.chat_io import CONVERSATION_ID_MAX_LENGTH

#: ``agent.config`` 中标记「对外暴露为 A2A Server」的键。
A2A_PUBLISH_FLAG = "a2a_publish"

#: Agent Card 声明的协议版本与传输绑定。
#: 取值 0.3：本模块产出的方法名（``message/*``、``tasks/*``）与线格式（``kind`` 判别字段、
#: 小写 TaskState）都是 v0.3 形状。声明 1.0 会让对端按 PascalCase 方法名调用并撞 ``-32601``。
A2A_PROTOCOL_VERSION = "0.3"
A2A_PROTOCOL_BINDING = "JSONRPC"

#: ``securitySchemes`` / ``security`` 中引用该方案的键名。
A2A_SECURITY_SCHEME = "apiKey"

#: JSON-RPC 2.0 错误码（A2A 沿用）。
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

#: A2A 应用级错误码（spec §JSON-RPC，-32000..-32099 区间）。
TASK_NOT_FOUND = -32001
TASK_NOT_CANCELABLE = -32002

#: 限流拒绝。规范把 -32000..-32099 留给实现自定义（A2A 已占 -32001..-32007），
#: 并要求自定义码「清楚地记录」—— 故写入 docs/guides/a2a.md。
RATE_LIMITED = -32000

#: 租户审计 ``action``（落 ``aud_logs``）。只记「谁在何时以何结果调了什么」——
#: ``aud_logs`` 是租户可见面，不写消息正文（正文可能含隐私内容）。
AUDIT_ACTION_MESSAGE_SEND = "a2a.message.send"
AUDIT_ACTION_MESSAGE_STREAM = "a2a.message.stream"
AUDIT_ACTION_TASKS_GET = "a2a.tasks.get"
AUDIT_ACTION_TASKS_CANCEL = "a2a.tasks.cancel"
AUDIT_ACTION_ARTIFACT_DOWNLOAD = "a2a.artifact.download"

#: 审计 ``detail.outcome`` 取值。
AUDIT_OUTCOME_OK = "ok"
AUDIT_OUTCOME_REJECTED = "rejected"
AUDIT_OUTCOME_FAILED = "failed"
AUDIT_OUTCOME_CANCELED = "canceled"

#: A2A ``TaskState``（v0.3）。
TASK_STATE_SUBMITTED = "submitted"
TASK_STATE_WORKING = "working"
TASK_STATE_COMPLETED = "completed"
TASK_STATE_FAILED = "failed"
TASK_STATE_CANCELED = "canceled"
TASK_STATE_REJECTED = "rejected"
TASK_STATE_UNKNOWN = "unknown"

#: 平台生成任务状态（``GenerativeJobStatus``）→ A2A ``TaskState``。
#: 不 import 平台枚举：本模块为纯逻辑，且枚举在 ORM 包内。
_JOB_STATUS_TO_TASK_STATE = {
    "pending": TASK_STATE_SUBMITTED,
    "running": TASK_STATE_WORKING,
    "success": TASK_STATE_COMPLETED,
    "failed": TASK_STATE_FAILED,
    "cancelled": TASK_STATE_CANCELED,
}

#: 生成任务终态：到达后无轮询/取消价值。
_TERMINAL_JOB_STATUSES = frozenset({"success", "failed", "cancelled"})


def to_a2a_task_state(job_status: str) -> str:
    """平台生成任务状态 → A2A ``TaskState``。

    未知状态回 A2A 保留值 ``unknown`` 而非猜测：把未知当成 ``completed`` 会让对端
    以为产物已就绪并停止轮询。
    """
    return _JOB_STATUS_TO_TASK_STATE.get(job_status, TASK_STATE_UNKNOWN)


def is_active_generative_status(status: object) -> bool:
    """该生成任务是否「未到终态」，值得对外返回 ``Task`` 供轮询。

    只排除明确终态（success/failed/cancelled）：未知状态一律视为进行中，与
    ``to_a2a_task_state`` 对未知状态回 ``unknown``（而非 ``completed``）同一原则 ——
    宁可让对端多轮询一次，也不谎称产物已就绪。
    """
    return not (isinstance(status, str) and status in _TERMINAL_JOB_STATUSES)


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
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "defaultInputModes": ["text"],
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


def extract_message_context_id(params: dict) -> str | None:
    """取 A2A ``message/send`` 的 ``message.contextId``（多轮上下文标识）。

    缺省或非字符串视为「无上下文」返回 ``None``：首轮调用本就不带，不能因此报错。
    超长则抛 ``BadRequestError`` —— 它作为 ``conversation_id`` 会被下游契约的
    ``max_length`` 拒绝并退化成 500，在入口判为参数错误更可诊断。
    """
    message = params.get("message")
    if not isinstance(message, dict):
        return None
    raw = message.get("contextId")
    if not isinstance(raw, str):
        return None
    context_id = raw.strip()
    if not context_id:
        return None
    if len(context_id) > CONVERSATION_ID_MAX_LENGTH:
        raise BadRequestError(f"message.contextId 过长（上限 {CONVERSATION_ID_MAX_LENGTH} 字符）")
    return context_id


def build_a2a_task(
    *,
    task_id: str,
    context_id: str | None,
    state: str,
    timestamp: str,
    artifacts: list[dict] | None = None,
) -> dict:
    """构造 A2A ``Task``。

    ``contextId`` / ``artifacts`` 均为可选：解析不到就省略而非塞空值；``history`` 暂不
    产出（对端的原始消息本就在请求里）。
    """
    task: dict = {
        "kind": "task",
        "id": task_id,
        "status": {"state": state, "timestamp": timestamp},
    }
    if context_id:
        task["contextId"] = context_id
    if artifacts:
        task["artifacts"] = artifacts
    return task


def build_a2a_agent_message(*, text: str, context_id: str, task_id: str | None = None) -> dict:
    """A2A ``Message``（agent 角色）。

    ``contextId`` 必须回显：对端据此把后续消息接回同一上下文，否则每轮都是新对话。
    ``taskId`` 仅在该消息属于某个 Task 时带上（流式帧的嵌套消息带，``message/send``
    的同步回答不带 —— 同步回答不产生任务）。
    """
    message: dict = {
        "kind": "message",
        "role": "agent",
        "messageId": str(uuid4()),
        "contextId": context_id,
        "parts": [{"kind": "text", "text": text}],
    }
    if task_id:
        message["taskId"] = task_id
    return message


def build_a2a_status_update(
    *,
    task_id: str,
    context_id: str,
    state: str,
    timestamp: str,
    text: str | None = None,
    final: bool = False,
    job_task_id: str | None = None,
) -> dict:
    """A2A ``TaskStatusUpdateEvent``（``message/stream`` 的帧载荷）。

    ``final`` 表示「本流结束」，不等于「任务终态」—— 产生异步生成任务时以
    ``working`` + ``final=True`` 收尾，对端再转向 ``tasks/get`` 轮询。

    ``job_task_id`` 非空时写入嵌套消息的 ``metadata.a2aJobTaskId``：本流的 taskId 是
    合成的（流开始时就得定），生成任务 id 只有跑完才知道，故不强行合一，改用该扩展位
    把两者串起来。
    """
    status: dict = {"state": state, "timestamp": timestamp}
    if text is not None:
        message = build_a2a_agent_message(text=text, context_id=context_id, task_id=task_id)
        if job_task_id:
            message["metadata"] = {"a2aJobTaskId": job_task_id}
        status["message"] = message
    return {
        "kind": "status-update",
        "taskId": task_id,
        "contextId": context_id,
        "status": status,
        "final": final,
    }


def artifact_ids_from_job_result(job_result: object) -> list[str]:
    """从生成任务 ``result`` 取产物附件 ID。

    生图是多产物（``attachment_ids``），生视频单个（``attachment_id``）；去重并丢弃空值，
    否则会产出指向 ``None`` 的下载地址。
    """
    if not isinstance(job_result, dict):
        return []
    raw = job_result.get("attachment_ids")
    candidates = list(raw) if isinstance(raw, list) else []
    single = job_result.get("attachment_id")
    if single:
        candidates.append(single)

    ids: list[str] = []
    for item in candidates:
        if isinstance(item, str) and item.strip() and item not in ids:
            ids.append(item)
    return ids


def build_a2a_artifacts(
    *,
    job_result: object,
    agent_id: UUID | str,
    task_id: UUID | str,
    base_url: str,
) -> list[dict]:
    """生成任务产物 → A2A ``Artifact`` 列表。

    ``file.uri`` 指向本平台的开放下载端点（**需 ``X-API-Key``**），而非对象存储签名 URL
    —— 与平台「不以签名链接外泄文件」的既有取向一致。
    """
    if not isinstance(job_result, dict):
        return []
    mime_type = job_result.get("mime_type")
    kind = job_result.get("kind")
    artifacts: list[dict] = []
    for index, attachment_id in enumerate(artifact_ids_from_job_result(job_result)):
        file: dict = {"uri": f"{base_url.rstrip('/')}{a2a_task_artifact_path(agent_id, task_id, attachment_id)}"}
        if isinstance(mime_type, str) and mime_type:
            file["mimeType"] = mime_type
        if isinstance(kind, str) and kind:
            file["name"] = f"{kind}-{index + 1}"
        artifacts.append(
            {
                "artifactId": attachment_id,
                "parts": [{"kind": "file", "file": file}],
            }
        )
    return artifacts


def jsonrpc_result(req_id: object, result: dict) -> dict:
    """JSON-RPC 2.0 成功信封。"""
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def jsonrpc_error(req_id: object, code: int, message: str, data: dict | None = None) -> dict:
    """JSON-RPC 2.0 错误信封；``data`` 非空时附结构化细节（规范允许）。"""
    error: dict = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}
