"""
ComplianceService 门面。

通过 Mixin 组合 intercept / library / entry 等子模块；具体方法见各模块文件。
对外仅从此包 ``__init__.py`` 或本模块导入 ``ComplianceService``。
"""

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.service import BaseService
from app.core.tenant import TenantContext
from app.tenant.compliance.meta import compliance_meta_dict
from app.tenant.compliance.schemas.meta import ComplianceMetaOut
from app.tenant.compliance.services.compliance.entry import WordEntryMixin
from app.tenant.compliance.services.compliance.intercept import ComplianceInterceptMixin
from app.tenant.compliance.services.compliance.library import WordLibraryMixin
from app.tenant.compliance.services.compliance.library_words import LibraryWordMixin
from app.tenant.compliance.services.compliance.logs import InterceptLogMixin
from app.tenant.compliance.services.compliance.scan_bindings import ComplianceScanBindingsMixin


class ComplianceService(
    InterceptLogMixin,
    WordEntryMixin,
    LibraryWordMixin,
    ComplianceScanBindingsMixin,
    WordLibraryMixin,
    ComplianceInterceptMixin,
    BaseService,
):
    """合规服务门面（Mixin 组合）。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        """注入数据库会话与租户上下文。"""
        super().__init__(db, ctx)

    async def get_meta(self) -> ComplianceMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return ComplianceMetaOut.model_validate(compliance_meta_dict())
