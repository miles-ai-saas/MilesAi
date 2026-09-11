"""钩子枚举展示元数据（GET /hooks/meta）。

- triggers（含 implemented 接线状态）/ scopes / on_failure_options / response_actions
- _TRIGGER_IMPLEMENTED 与运行时接线一致；hooks.md §4 须同步
- 前端：hooks/use-hook-meta.ts；列表/表单用 optionLabel(meta?.triggers, …)
- 约定：docs/guides/hooks.md §9
"""

from __future__ import annotations

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption, literal_options
from miles_portal.tenant.hooks.models import HookScope, HookTrigger

# 与运行时接线保持一致；文档 hooks.md §4 须同步
_TRIGGER_IMPLEMENTED: dict[HookTrigger, bool] = {
    HookTrigger.BEFORE_CALL: True,
    HookTrigger.AFTER_CALL: True,
    HookTrigger.BEFORE_REASONING: True,  # 直连 / RAG；不含画布内每节点
    HookTrigger.AFTER_REASONING: True,
    HookTrigger.BEFORE_TOOL: True,
    HookTrigger.AFTER_TOOL: True,
    HookTrigger.ON_ERROR: True,
}

_TRIGGER_LABELS: dict[HookTrigger, tuple[str, str]] = {
    HookTrigger.BEFORE_CALL: ("调用前", "对话或流程 run 开始前"),
    HookTrigger.AFTER_CALL: ("调用后", "成功返回后"),
    HookTrigger.BEFORE_REASONING: ("推理前", "主 LLM 调用前"),
    HookTrigger.AFTER_REASONING: ("推理后", "主 LLM 调用后"),
    HookTrigger.BEFORE_TOOL: ("工具前", "工具 invoke 前"),
    HookTrigger.AFTER_TOOL: ("工具后", "工具 invoke 后"),
    HookTrigger.ON_ERROR: ("出错时", "未捕获异常"),
}

_SCOPE_LABELS: dict[HookScope, tuple[str, str]] = {
    HookScope.GLOBAL: ("全局", "租户内该时机下全部资源"),
    HookScope.AGENT: ("智能体", "指定 agent_id"),
    HookScope.FLOW: ("流程", "指定 flow_id"),
    HookScope.TOOL: ("工具", "指定 tool_id"),
    HookScope.APP: ("应用", "预留，市场应用级"),
}

ON_FAILURE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("ignore", "忽略并继续", None),
    ("fail_request", "阻断请求", "仅 before_* 且 HTTP/网络失败时"),
]

RESPONSE_ACTION_OPTIONS: list[tuple[str, str, str | None]] = [
    ("continue", "继续", None),
    ("block", "拦截", None),
    ("modify", "改写字段", None),
]


def hook_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    triggers = [
        EnumOption(
            value=t.value,
            label=_TRIGGER_LABELS[t][0],
            hint=_TRIGGER_LABELS[t][1],
            implemented=_TRIGGER_IMPLEMENTED.get(t, False),
        )
        for t in HookTrigger
    ]
    scopes = [
        EnumOption(
            value=s.value,
            label=_SCOPE_LABELS[s][0],
            hint=_SCOPE_LABELS[s][1],
        )
        for s in HookScope
    ]
    return {
        "triggers": triggers,
        "scopes": scopes,
        "on_failure_options": literal_options(ON_FAILURE_OPTIONS),
        "response_actions": literal_options(RESPONSE_ACTION_OPTIONS),
        "schema_version": META_SCHEMA_VERSION,
    }
