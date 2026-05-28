"""附件枚举展示元数据（GET /attachments/meta）。

- purposes / purpose_filters（筛选含空值=全部）
- 前端：lib/attachment-labels.ts、hooks/use-attachment-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, literal_options

PURPOSE_FILTER_OPTIONS: list[tuple[str, str, str | None]] = [
    ("", "全部用途", None),
    ("general", "通用", "默认上传用途"),
    ("chat", "对话", "会话消息附件"),
    ("agent", "智能体", "智能体配置相关文件"),
    ("flow", "流程", "流程画布或运行附件"),
    ("chat_generated", "对话生成", "智能体生图/生视频产出"),
    ("flow_generated", "流程生成", "流程生图/生视频节点产出"),
]

PURPOSE_OPTIONS: list[tuple[str, str, str | None]] = [(v, lb, h) for v, lb, h in PURPOSE_FILTER_OPTIONS if v]


def attachments_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "purposes": literal_options(PURPOSE_OPTIONS),
        "purpose_filters": literal_options(PURPOSE_FILTER_OPTIONS),
        "schema_version": META_SCHEMA_VERSION,
    }
