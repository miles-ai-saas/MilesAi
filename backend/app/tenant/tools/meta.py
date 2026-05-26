"""工具枚举展示元数据（GET /tools/meta）。

- tool_types / catalog_sources / invocation_statuses
- 前端：lib/tool-labels.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption, enum_options, literal_options
from app.tenant.tools.models import ToolType

TOOL_TYPE_LABELS: dict[str, tuple[str, str | None]] = {
    ToolType.HTTP.value: ("HTTP", "调用 REST API，支持 URL 模板与参数映射"),
    ToolType.SCRIPT.value: ("Python 脚本", "在 MCP Runner 沙箱内运行，须定义 run(params)"),
}

CATALOG_SOURCE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("", "全部", "内置 + 自定义"),
    ("builtin", "内置", "平台预置工具"),
    ("custom", "自定义", "租户自建 HTTP / 脚本"),
]

INVOCATION_STATUS_OPTIONS: list[tuple[str, str, str | None]] = [
    ("success", "成功", None),
    ("error", "失败", None),
    ("confirmation_required", "待确认", "需用户确认后执行"),
]


def tools_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "tool_types": enum_options(ToolType, TOOL_TYPE_LABELS),
        "catalog_sources": literal_options(CATALOG_SOURCE_OPTIONS),
        "invocation_statuses": literal_options(INVOCATION_STATUS_OPTIONS),
        "schema_version": META_SCHEMA_VERSION,
    }
