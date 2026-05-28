"""租户级敏感词条（可多库关联）。"""

from uuid import UUID
from sqlalchemy import select
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.tenant import assert_tenant_access
from app.tenant.compliance.models import LibraryWordBinding, SensitiveWordEntry, WordLibrary
from app.tenant.compliance.schemas.compliance import (
    EntryLibrariesUpdate,
    EntryLibraryRef,
    SensitiveWordEntryOut,
)


class WordEntryMixin:
    """租户级敏感词条及多库关联。"""

    async def get_entry(self, entry_id: UUID) -> SensitiveWordEntryOut:
        """获取敏感词条及所属词库列表。"""
        entry = await self.get_entry_or_raise(entry_id)
        return await self.entry_out(entry)

    async def set_entry_libraries(self, entry_id: UUID, body: EntryLibrariesUpdate) -> SensitiveWordEntryOut:
        """全量更新词条关联的词库集合。"""
        entry = await self.get_entry_or_raise(entry_id)
        wanted = set(body.library_ids)
        if wanted:
            found = (
                (
                    await self.db.execute(
                        select(WordLibrary.id).where(
                            WordLibrary.id.in_(wanted),
                            WordLibrary.tenant_id == entry.tenant_id,
                            not_deleted(WordLibrary),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if len(found) != len(wanted):
                raise BadRequestError("部分词库不存在")
        existing = (
            (await self.db.execute(select(LibraryWordBinding).where(LibraryWordBinding.entry_id == entry_id, not_deleted(LibraryWordBinding)))).scalars().all()
        )
        by_lib = {b.library_id: b for b in existing}
        for lib_id, binding in list(by_lib.items()):
            if lib_id not in wanted:
                await mark_deleted(self.db, binding)
        for lib_id in wanted:
            if lib_id not in by_lib:
                self.db.add(
                    LibraryWordBinding(
                        library_id=lib_id,
                        entry_id=entry_id,
                        action=body.default_action,
                        is_active=True,
                    )
                )
        await self.db.flush()
        return await self.entry_out(entry)

    async def get_entry_or_raise(self, entry_id: UUID) -> SensitiveWordEntry:
        """加载词条并校验租户。"""
        row = await self.db.get(SensitiveWordEntry, entry_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("词条不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def entry_out(self, entry: SensitiveWordEntry) -> SensitiveWordEntryOut:
        """组装 ``SensitiveWordEntryOut``。"""
        stmt = (
            select(LibraryWordBinding, WordLibrary.name)
            .join(WordLibrary, WordLibrary.id == LibraryWordBinding.library_id)
            .where(
                LibraryWordBinding.entry_id == entry.id,
                not_deleted(LibraryWordBinding),
                not_deleted(WordLibrary),
            )
        )
        rows = (await self.db.execute(stmt)).all()
        refs = [
            EntryLibraryRef(
                library_id=b.library_id,
                library_name=name,
                binding_id=b.id,
                action=b.action,
                is_active=b.is_active,
            )
            for b, name in rows
        ]
        return SensitiveWordEntryOut(
            id=entry.id,
            tenant_id=entry.tenant_id,
            word=entry.word,
            libraries=refs,
            created_at=entry.created_at,
        )
