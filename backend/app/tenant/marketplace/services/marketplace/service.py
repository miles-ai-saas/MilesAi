"""
MarketplaceService 门面。

通过 Mixin 组合 catalog / publish / install 等子模块；``__init__`` 注入 flow/agent/kb 仓库。
对外仅从此包 ``__init__.py`` 导入 ``MarketplaceService``。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.service import BaseService
from app.core.tenant import TenantContext
from app.tenant.agents.repositories.agent import AgentRepository
from app.tenant.flows.repositories.flow import FlowRepository
from app.tenant.kb.repositories.kb import KnowledgeBaseRepository
from app.tenant.marketplace.meta import marketplace_meta_dict
from app.tenant.marketplace.schemas.meta import MarketplaceMetaOut
from app.tenant.marketplace.services.marketplace.catalog import MarketplaceCatalogMixin
from app.tenant.marketplace.services.marketplace.install import MarketplaceInstallMixin
from app.tenant.marketplace.services.marketplace.publish import MarketplacePublishMixin
from app.tenant.marketplace.services.marketplace.ratings import MarketplaceRatingsMixin
from app.tenant.marketplace.services.marketplace.review import MarketplaceReviewMixin
from app.tenant.marketplace.services.marketplace.upgrade import MarketplaceUpgradeMixin


class MarketplaceService(
    MarketplaceRatingsMixin,
    MarketplaceReviewMixin,
    MarketplaceUpgradeMixin,
    MarketplaceInstallMixin,
    MarketplacePublishMixin,
    MarketplaceCatalogMixin,
    BaseService,
):
    """应用市场服务门面；安装时按 manifest 深拷贝资源。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        """注入数据库会话、租户上下文及 flow/agent/kb 仓库。"""
        super().__init__(db, ctx)
        self.flow_repo = FlowRepository(db)
        self.agent_repo = AgentRepository(db)
        self.kb_repo = KnowledgeBaseRepository(db)

    async def get_meta(self) -> MarketplaceMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return MarketplaceMetaOut.model_validate(marketplace_meta_dict())
