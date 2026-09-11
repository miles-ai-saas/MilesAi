"""媒体资产仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.repository import BaseRepository
from miles_core.models.media.media_asset import MediaAsset


class MediaAssetRepository(BaseRepository[MediaAsset]):
    """媒体资产仓储；继承通用 CRUD，无额外查询。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, MediaAsset)
