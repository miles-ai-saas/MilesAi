from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.models.attachment import Attachment


class AttachmentRepository(BaseRepository[Attachment]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Attachment)
