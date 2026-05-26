"""流程枚举展示元数据（GET /flows/meta）。

- statuses：FlowStatus（draft / published）
- 前端：lib/flow-labels.ts、hooks/use-flow-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import enum_options
from app.models.flow import FlowStatus

FLOW_STATUS_LABELS: dict[str, tuple[str, str | None]] = {
    FlowStatus.DRAFT.value: ("草稿", "未发布，不可绑定智能体"),
    FlowStatus.PUBLISHED.value: ("已发布", "可绑定智能体并运行"),
}


def flow_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "statuses": enum_options(FlowStatus, FLOW_STATUS_LABELS),
    }
