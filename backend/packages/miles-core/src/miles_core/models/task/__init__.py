"""异步任务记录 ORM（task_records）。"""

from miles_core.models.task.task_record import CeleryTaskRecord, TaskStatus

__all__ = ["CeleryTaskRecord", "TaskStatus"]
