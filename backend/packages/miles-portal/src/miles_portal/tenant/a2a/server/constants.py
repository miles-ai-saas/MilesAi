"""A2A Server 协议常量与生成任务状态映射（纯逻辑）。"""

from __future__ import annotations

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

#: 限流拒绝。规范把 -32000..-32099 留给实现自定义（本实现已占 `-32001` / `-32002`），
#: 并要求自定义码「清楚地记录」—— 故写入 docs/guides/a2a.md。
RATE_LIMITED = -32000

#: 归属 ``tasks/*`` 域的方法前缀。该域的 401/403/404 压成 ``TASK_NOT_FOUND``，
#: 否则跨租户任务回 ``-32602``（参数错）会与「任务不存在」可区分 —— 存在性 oracle
#: 会从另一条路放回来（上一批刚收口掉的那个问题）。
_TASKS_METHOD_PREFIX = "tasks/"

#: 租户审计 ``action``（落 ``aud_logs``）。只记「谁在何时以何结果调了什么」——
#: ``aud_logs`` 是租户可见面，不写消息正文（正文可能含隐私内容）。
AUDIT_ACTION_MESSAGE_SEND = "a2a.message.send"
AUDIT_ACTION_MESSAGE_STREAM = "a2a.message.stream"
AUDIT_ACTION_TASKS_GET = "a2a.tasks.get"
AUDIT_ACTION_TASKS_CANCEL = "a2a.tasks.cancel"
AUDIT_ACTION_ARTIFACT_DOWNLOAD = "a2a.artifact.download"
AUDIT_ACTION_TASKS_RESUBSCRIBE = "a2a.tasks.resubscribe"
AUDIT_ACTION_PUSH_CONFIG_SET = "a2a.tasks.pushNotificationConfig.set"
AUDIT_ACTION_PUSH_CONFIG_GET = "a2a.tasks.pushNotificationConfig.get"
AUDIT_ACTION_PUSH_CONFIG_LIST = "a2a.tasks.pushNotificationConfig.list"
AUDIT_ACTION_PUSH_CONFIG_DELETE = "a2a.tasks.pushNotificationConfig.delete"

#: ``tasks/pushNotificationConfig/*`` 四方法。
PUSH_NOTIFICATION_METHODS = frozenset(
    {
        "tasks/pushNotificationConfig/set",
        "tasks/pushNotificationConfig/get",
        "tasks/pushNotificationConfig/list",
        "tasks/pushNotificationConfig/delete",
    }
)

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


def is_terminal_generative_status(status: object) -> bool:
    """该生成任务是否已到终态（``success`` / ``failed`` / ``cancelled``）。

    只认明确的终态字符串：未知状态视为**未**终态，与 ``to_a2a_task_state`` 对未知回
    ``unknown``（而非 ``completed``）同一原则 —— 宁可让对端多轮询/多收一帧，也不谎称产物已就绪。
    """
    return isinstance(status, str) and status in _TERMINAL_JOB_STATUSES


def is_active_generative_status(status: object) -> bool:
    """该生成任务是否「未到终态」，值得对外返回 ``Task`` 供轮询。

    只是 ``is_terminal_generative_status`` 的反面，判据单一来源。
    """
    return not is_terminal_generative_status(status)

