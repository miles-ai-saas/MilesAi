"""媒体资产仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.models.media_asset import MediaAsset


class MediaAssetRepository(BaseRepository[MediaAsset]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, MediaAsset)
