"""标签枚举展示元数据（GET /tags/meta）。

- ``entity_types``：标签可绑定的资源类型（agent/prompt/skill/tool/flow）
- 前端：lib/tag-labels.ts、hooks/use-tag-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, enum_options
from app.models.meta.tag import TagEntityType

ENTITY_TYPE_LABELS: dict[str, tuple[str, str | None]] = {
    TagEntityType.AGENT.value: ("智能体", "绑定 agt_agents"),
    TagEntityType.PROMPT.value: ("提示词", "绑定 prompt_templates"),
    TagEntityType.SKILL.value: ("技能包", "绑定 skill_packages"),
    TagEntityType.TOOL.value: ("工具", "绑定 tools"),
    TagEntityType.FLOW.value: ("流程", "绑定 flow_flows"),
    TagEntityType.MARKETPLACE_APP.value: ("应用市场", "绑定 mkt_apps"),
}


def tags_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "entity_types": enum_options(TagEntityType, ENTITY_TYPE_LABELS),
        "schema_version": META_SCHEMA_VERSION,
    }
