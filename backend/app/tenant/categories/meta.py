"""分类枚举展示元数据（GET /categories/meta）。

- ``domains``：各资源域（agent/prompt/skill/tool）的 Tab/筛选展示名
- 具体分类名称仍由 GET /categories?domain= 拉取 sys_categories 实例
- 前端：lib/category-labels.ts、hooks/use-category-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, enum_options
from app.models.category import CategoryDomain

# value 与 CategoryDomain 存库一致
DOMAIN_LABELS: dict[str, tuple[str, str | None]] = {
    CategoryDomain.AGENT.value: ("智能体", "agt_agents 列表 Tab / 单选分类"),
    CategoryDomain.PROMPT.value: ("提示词", "prompt_templates 列表 Tab"),
    CategoryDomain.SKILL.value: ("技能包", "skill_packages 列表 Tab"),
    CategoryDomain.TOOL.value: ("工具", "tools 列表 Tab"),
}


def categories_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "domains": enum_options(CategoryDomain, DOMAIN_LABELS),
        "schema_version": META_SCHEMA_VERSION,
    }
