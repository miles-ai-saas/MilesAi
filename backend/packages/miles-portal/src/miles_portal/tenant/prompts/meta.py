"""提示词模板枚举展示元数据（GET /prompt-templates/meta）。

- active_states：列表筛选与徽章（active / inactive）
- 前端：lib/prompt-labels.ts、hooks/use-prompt-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, literal_options

# 列表筛选 / 徽章展示（与 ORM is_active 布尔对应，前端用 String(active) 匹配）
ACTIVE_STATE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("active", "启用", "模板可被智能体引用"),
    ("inactive", "停用", "保留记录，新建时不可选"),
]


def prompts_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "active_states": literal_options(ACTIVE_STATE_OPTIONS),
        "schema_version": META_SCHEMA_VERSION,
    }
