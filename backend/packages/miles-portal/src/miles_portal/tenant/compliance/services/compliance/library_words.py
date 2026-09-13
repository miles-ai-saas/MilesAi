"""词库内词条绑定。"""

from uuid import UUID

from sqlalchemy import func, select

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_common.schema import PageParams, PageResult
from miles_core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from miles_core.tenant import assert_tenant_access
from miles_portal.tenant.compliance.models import LibraryWordBinding, SensitiveWordEntry, WordLibrary
from miles_portal.tenant.compliance.schemas.compliance import (
    LibraryWordBatchCreate,
    LibraryWordCreate,
    LibraryWordOut,
    LibraryWordUpdate,
)
from miles_portal.tenant.compliance.services.word_resolve import get_or_create_entry


class LibraryWordMixin:
    """词库内词条（绑定）维护。"""

    def binding_out(self, binding: LibraryWordBinding, word: str) -> LibraryWordOut:
        """组装 ``LibraryWordOut``。"""
        return LibraryWordOut(
            id=binding.id,
            library_id=binding.library_id,
            entry_id=binding.entry_id,
            word=word,
            action=binding.action,
            is_active=binding.is_active,
            created_at=binding.created_at,
        )

    async def list_library_words(self, library_id: UUID, params: PageParams) -> PageResult[LibraryWordOut]:
        """分页列出词库内词条。"""
        await self.get_library_or_raise(library_id)
        filters = [
            LibraryWordBinding.library_id == library_id,
            not_deleted(LibraryWordBinding),
            not_deleted(SensitiveWordEntry),
        ]
        total = await self.db.scalar(
            select(func.count()).select_from(LibraryWordBinding).join(SensitiveWordEntry, SensitiveWordEntry.id == LibraryWordBinding.entry_id).where(*filters)
        )
        stmt = (
            select(LibraryWordBinding, SensitiveWordEntry.word)
            .join(SensitiveWordEntry, SensitiveWordEntry.id == LibraryWordBinding.entry_id)
            .where(*filters)
            .order_by(LibraryWordBinding.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        rows = (await self.db.execute(stmt)).all()
        return PageResult(
            items=[self.binding_out(b, w) for b, w in rows],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def add_library_word(self, library_id: UUID, body: LibraryWordCreate) -> LibraryWordOut:
        """向词库添加词条（自动建 entry）。"""
        lib = await self.get_library_or_raise(library_id)
        entry = await get_or_create_entry(self.db, tenant_id=lib.tenant_id, word=body.word)
        existing = (
            await self.db.execute(
                select(LibraryWordBinding).where(
                    LibraryWordBinding.library_id == library_id,
                    LibraryWordBinding.entry_id == entry.id,
                    not_deleted(LibraryWordBinding),
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise BadRequestError("该词已存在于本词库")
        binding = LibraryWordBinding(library_id=library_id, entry_id=entry.id, action=body.action, is_active=body.is_active)
        self.db.add(binding)
        await self.db.flush()
        await self.db.refresh(binding)
        return self.binding_out(binding, entry.word)

    async def batch_add_library_words(self, library_id: UUID, body: LibraryWordBatchCreate) -> list[LibraryWordOut]:
        """批量添加词条（重复词跳过）。"""
        out: list[LibraryWordOut] = []
        for item in body.words:
            try:
                out.append(await self.add_library_word(library_id, item))
            except BadRequestError:
                continue
        return out

    async def update_library_word(self, library_id: UUID, binding_id: UUID, body: LibraryWordUpdate) -> LibraryWordOut:
        """更新库内词条绑定属性。"""
        await self.get_library_or_raise(library_id)
        binding = await self.get_binding_or_raise(binding_id, library_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(binding, k, v)
        await self.db.flush()
        entry = await self.db.get(SensitiveWordEntry, binding.entry_id)
        return self.binding_out(binding, entry.word if entry else "")

    async def delete_library_word(self, library_id: UUID, binding_id: UUID) -> None:
        """软删库内词条绑定。"""
        await self.get_library_or_raise(library_id)
        binding = await self.get_binding_or_raise(binding_id, library_id)
        await mark_deleted(self.db, binding)

    async def get_binding_or_raise(self, binding_id: UUID, library_id: UUID) -> LibraryWordBinding:
        """加载库内绑定并校验词库归属。"""
        row = await self.db.get(LibraryWordBinding, binding_id)
        if not row or is_marked_deleted(row) or row.library_id != library_id:
            raise NotFoundError("词条关联不存在")
        lib = await self.db.get(WordLibrary, library_id)
        if lib:
            assert_tenant_access(self.ctx, lib.tenant_id)
        return row
