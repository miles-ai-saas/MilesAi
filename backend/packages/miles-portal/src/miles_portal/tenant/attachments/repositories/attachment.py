"""附件表仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.repository import BaseRepository
from miles_core.models.media.attachment import Attachment


class AttachmentRepository(BaseRepository[Attachment]):
    """按 tenant_id + purpose/resource 过滤列表。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Attachment)
