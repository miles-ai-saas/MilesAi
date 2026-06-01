"""服务线模板包状态。"""

from enum import StrEnum


class TemplatePackStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
