"""生成任务业务异常。"""

from uuid import UUID

from miles_common.exceptions import BadRequestError


class GenerativeJobCancelled(BadRequestError):
    """任务已被用户取消。"""

    def __init__(self) -> None:
        super().__init__("生成任务已取消")


class GenerativeJobNotFound(Exception):
    """Celery worker 取任务时 DB 中找不到对应记录（事务未提交等）。"""

    def __init__(self, job_id: UUID) -> None:
        super().__init__(f"生成任务不存在: {job_id}")
