"""生成任务业务异常。"""

from app.common.exceptions import BadRequestError


class GenerativeJobCancelled(BadRequestError):
    """任务已被用户取消。"""

    def __init__(self) -> None:
        super().__init__("生成任务已取消")
