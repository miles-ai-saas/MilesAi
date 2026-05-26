"""租户扫描词库绑定。"""

from sqlalchemy import select
from app.common.exceptions import BadRequestError
from app.core.soft_delete import mark_deleted, not_deleted
from app.tenant.compliance.models import (
    COMPLIANCE_SCOPE_TENANT,
    ComplianceLibraryBinding,
    WordLibrary,
)
from app.tenant.compliance.schemas.compliance import (
    ComplianceScanBindingsOut,
    ComplianceScanBindingsUpdate,
)


class ComplianceScanBindingsMixin:
    """租户参与扫描的词库绑定维护。"""

    async def get_scan_bindings(self) -> ComplianceScanBindingsOut:
        """查询当前租户参与扫描的词库绑定。"""
        libs = await self.list_libraries_query(active_only=False)
        bound_ids = set(
            (
                await self.db.execute(
                    select(ComplianceLibraryBinding.library_id).where(
                        ComplianceLibraryBinding.tenant_id == self.ctx.tenant_id,
                        ComplianceLibraryBinding.scope == COMPLIANCE_SCOPE_TENANT,
                        not_deleted(ComplianceLibraryBinding),
                    )
                )
            )
            .scalars()
            .all()
        )
        out_libs = [await self.library_out(lib) for lib in libs]
        return ComplianceScanBindingsOut(library_ids=list(bound_ids), libraries=out_libs)

    async def set_scan_bindings(
        self, body: ComplianceScanBindingsUpdate
    ) -> ComplianceScanBindingsOut:
        """全量更新租户扫描词库绑定。"""
        wanted = set(body.library_ids)
        if wanted:
            found = (
                (
                    await self.db.execute(
                        select(WordLibrary.id).where(
                            WordLibrary.id.in_(wanted),
                            WordLibrary.tenant_id == self.ctx.tenant_id,
                            not_deleted(WordLibrary),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if len(found) != len(wanted):
                raise BadRequestError("部分词库不存在或无权访问")
        existing = (
            (
                await self.db.execute(
                    select(ComplianceLibraryBinding).where(
                        ComplianceLibraryBinding.tenant_id == self.ctx.tenant_id,
                        ComplianceLibraryBinding.scope == COMPLIANCE_SCOPE_TENANT,
                        not_deleted(ComplianceLibraryBinding),
                    )
                )
            )
            .scalars()
            .all()
        )
        existing_map = {b.library_id: b for b in existing}
        for lib_id, row in list(existing_map.items()):
            if lib_id not in wanted:
                await mark_deleted(self.db, row)
        for lib_id in wanted:
            if lib_id not in existing_map:
                self.db.add(
                    ComplianceLibraryBinding(
                        tenant_id=self.ctx.tenant_id,
                        library_id=lib_id,
                        scope=COMPLIANCE_SCOPE_TENANT,
                    )
                )
        await self.db.flush()
        return await self.get_scan_bindings()
