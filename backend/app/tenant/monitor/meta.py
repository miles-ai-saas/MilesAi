"""监控枚举展示元数据（GET /monitor/meta）。

- health_components / overall_health_statuses / trend_day_ranges
- 前端：lib/monitor-labels.ts、hooks/use-monitor-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import literal_options

HEALTH_COMPONENT_OPTIONS: list[tuple[str, str, str | None]] = [
    ("postgres", "PostgreSQL", "主库连通性"),
    ("redis", "Redis", "缓存与 LangGraph checkpoint"),
    ("vector_store", "向量库", "当前 VECTOR_STORE_BACKEND"),
    ("object_storage", "对象存储", "MinIO/S3 兼容存储"),
    ("weaviate", "Weaviate", "兼容别名，非主后端时可忽略"),
    ("minio", "MinIO", "兼容别名"),
]

OVERALL_HEALTH_STATUS_OPTIONS: list[tuple[str, str, str | None]] = [
    ("healthy", "正常", None),
    ("degraded", "降级", "部分组件不可用"),
    ("unhealthy", "异常", "关键依赖不可用"),
]

TREND_DAY_OPTIONS: list[tuple[str, str, str | None]] = [
    ("7", "近 7 天", None),
    ("14", "近 14 天", None),
    ("30", "近 30 天", None),
]


def monitor_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "health_components": literal_options(HEALTH_COMPONENT_OPTIONS),
        "overall_health_statuses": literal_options(OVERALL_HEALTH_STATUS_OPTIONS),
        "trend_day_ranges": literal_options(TREND_DAY_OPTIONS),
        "schema_version": "1",
    }
