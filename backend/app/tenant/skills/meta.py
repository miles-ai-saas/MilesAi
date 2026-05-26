"""技能包枚举展示元数据（GET /skill-packages/meta）。

- source_types / active_states
- 前端：lib/skill-labels.ts、hooks/use-skill-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, literal_options

SOURCE_TYPE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("manual", "手动创建", "工作台创建空白技能包"),
    ("local", "本地目录", "从服务端可读路径装载"),
    ("zip", "ZIP 压缩包", "上传 zip 批量导入"),
    ("git", "Git 仓库", "浅克隆远端仓库导入"),
]

ACTIVE_STATE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("active", "启用", "可被智能体绑定"),
    ("inactive", "停用", "保留目录，绑定时忽略"),
]


def skills_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "source_types": literal_options(SOURCE_TYPE_OPTIONS),
        "active_states": literal_options(ACTIVE_STATE_OPTIONS),
        "schema_version": META_SCHEMA_VERSION,
    }
