"""A2A 枚举展示元数据（GET /a2a/peers/meta）。

- peer_statuses / invoke_policies / peer_role_hints（与 agents.meta 子角色共用）
- 前端：lib/a2a-labels.ts、hooks/use-a2a-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, enum_options, literal_options
from app.tenant.a2a.models import A2aPeerStatus
from app.tenant.agents.meta import SUB_AGENT_ROLE_OPTIONS

PEER_STATUS_LABELS: dict[str, tuple[str, str | None]] = {
    A2aPeerStatus.PENDING.value: ("待同步", "已登记，尚未拉取 Agent Card"),
    A2aPeerStatus.ACTIVE.value: ("已连通", "Card 同步成功，可被引用"),
    A2aPeerStatus.ERROR.value: ("异常", "同步失败，见 last_error"),
    A2aPeerStatus.INACTIVE.value: ("已停用", "保留登记，不参与编排"),
}

INVOKE_POLICY_OPTIONS: list[tuple[str, str, str | None]] = [
    ("rules_then_plan", "规则优先，未命中则自动规划", "默认策略"),
    ("rules_only", "仅规则触发", "按 trigger_keywords 匹配 Peer"),
    ("plan_only", "仅自动规划", "由主模型选择 Peer"),
]

# 与 agents.meta 子智能体 role_hint 一致（Peer 引用 / 宿主绑定）
PEER_ROLE_HINT_OPTIONS: list[tuple[str, str, str | None]] = [
    (v, lb, h) for v, lb, h in SUB_AGENT_ROLE_OPTIONS if v
]


def a2a_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "peer_statuses": enum_options(A2aPeerStatus, PEER_STATUS_LABELS),
        "invoke_policies": literal_options(INVOKE_POLICY_OPTIONS),
        "peer_role_hints": literal_options(PEER_ROLE_HINT_OPTIONS),
        "schema_version": META_SCHEMA_VERSION,
    }
