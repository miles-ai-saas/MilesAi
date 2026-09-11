"""模型配置仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.models.model import ModelConfig


class ModelConfigRepository(BaseRepository[ModelConfig]):
    """内置/自定义模型配置的持久化访问。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ModelConfig)
