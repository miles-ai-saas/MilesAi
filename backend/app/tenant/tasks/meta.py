"""异步任务枚举展示元数据（GET /tasks/meta）。

- statuses / status_filters（筛选含空值=全部）
- 前端：lib/task-labels.ts、hooks/use-task-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, enum_options, literal_options
from app.models.task import TaskStatus

TASK_STATUS_LABELS: dict[str, tuple[str, str | None]] = {
    TaskStatus.PENDING.value: ("等待中", "已投递，尚未执行"),
    TaskStatus.RUNNING.value: ("运行中", "Worker 正在处理"),
    TaskStatus.SUCCESS.value: ("成功", "已完成"),
    TaskStatus.FAILED.value: ("失败", "见 fail_reason"),
    TaskStatus.CANCELLED.value: ("已取消", "用户或系统取消"),
}

STATUS_FILTER_OPTIONS: list[tuple[str, str, str | None]] = [
    ("", "全部", None),
    *[(s.value, TASK_STATUS_LABELS[s.value][0], TASK_STATUS_LABELS[s.value][1]) for s in TaskStatus],
]


def tasks_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "statuses": enum_options(TaskStatus, TASK_STATUS_LABELS),
        "status_filters": literal_options(STATUS_FILTER_OPTIONS),
        "schema_version": META_SCHEMA_VERSION,
    }
