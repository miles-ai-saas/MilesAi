from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.models.model import ModelConfig


class ModelConfigRepository(BaseRepository[ModelConfig]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ModelConfig)
