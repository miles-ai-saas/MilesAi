"""业务中心站内通知 schema。"""

from pydantic import BaseModel

from app.biz.schemas.milestone import BizMilestoneDueOut


class BizNotificationsOut(BaseModel):
    """业务中心提醒摘要（里程碑到期等）。"""

    due_milestone_count: int
    due_milestones: list[BizMilestoneDueOut]
