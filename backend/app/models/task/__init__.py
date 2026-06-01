"""异步任务记录 ORM（task_records）。"""

from app.models.task.task_record import CeleryTaskRecord, TaskStatus

__all__ = ["TaskStatus", "CeleryTaskRecord"]
