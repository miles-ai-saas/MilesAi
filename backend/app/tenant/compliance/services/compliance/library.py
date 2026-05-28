"""敏感词词库 CRUD。"""

from uuid import UUID
from sqlalchemy import func, select
from app.common.exceptions import NotFoundError
from app.common.schema import PageParams, PageResult
from app.core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted, not_deleted
from app.core.tenant import assert_tenant_access, tenant_filters
from app.tenant.compliance.models import (
    DEFAULT_WORD_LIBRARY_NAME,
    ComplianceLibraryBinding,
    LibraryWordBinding,
    SensitiveWordEntry,
    WordLibrary,
)
from app.tenant.compliance.schemas.compliance import (
    WordLibraryCreate,
    WordLibraryOut,
    WordLibraryUpdate,
)


class WordLibraryMixin:
    """敏感词词库 CRUD 与输出组装。"""

    async def count_words_in_library(self, library_id: UUID) -> int:
        """统计词库内有效词条数量。"""
        return int(
            await self.db.scalar(
                select(func.count())
                .select_from(LibraryWordBinding)
                .join(SensitiveWordEntry, SensitiveWordEntry.id == LibraryWordBinding.entry_id)
                .where(
                    LibraryWordBinding.library_id == library_id,
                    not_deleted(LibraryWordBinding),
                    not_deleted(SensitiveWordEntry),
                )
            )
            or 0
        )

    async def library_out(self, lib: WordLibrary) -> WordLibraryOut:
        """组装带 ``word_count`` 的 ``WordLibraryOut``。"""
        count = await self.count_words_in_library(lib.id)
        data = WordLibraryOut.model_validate(lib)
        return data.model_copy(update={"word_count": count})

    async def list_libraries_query(self, *, active_only: bool) -> list[WordLibrary]:
        """查询词库列表（可选仅启用）。"""
        filters = append_not_deleted(tenant_filters(self.ctx, WordLibrary.tenant_id), WordLibrary)
        if active_only:
            filters.append(WordLibrary.is_active.is_(True))
        stmt = select(WordLibrary).where(*filters).order_by(WordLibrary.sort_order.asc(), WordLibrary.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_libraries(self, params: PageParams) -> PageResult[WordLibraryOut]:
        """分页列出词库。"""
        filters = append_not_deleted(tenant_filters(self.ctx, WordLibrary.tenant_id), WordLibrary)
        total = await self.db.scalar(select(func.count()).select_from(WordLibrary).where(*filters))
        stmt = (
            select(WordLibrary)
            .where(*filters)
            .order_by(WordLibrary.sort_order.asc(), WordLibrary.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[await self.library_out(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_library(self, body: WordLibraryCreate) -> WordLibraryOut:
        """创建词库。"""
        row = WordLibrary(
            tenant_id=self.ctx.tenant_id,
            name=body.name.strip(),
            description=body.description,
            is_active=body.is_active,
            sort_order=body.sort_order,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return await self.library_out(row)

    async def get_library(self, library_id: UUID) -> WordLibraryOut:
        """获取单个词库详情。"""
        row = await self.get_library_or_raise(library_id)
        return await self.library_out(row)

    async def update_library(self, library_id: UUID, body: WordLibraryUpdate) -> WordLibraryOut:
        """更新词库字段。"""
        row = await self.get_library_or_raise(library_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            if k == "name" and v is not None:
                setattr(row, k, v.strip())
            else:
                setattr(row, k, v)
        await self.db.flush()
        await self.db.refresh(row)
        return await self.library_out(row)

    async def delete_library(self, library_id: UUID) -> None:
        """软删词库及库内绑定、扫描绑定。"""
        row = await self.get_library_or_raise(library_id)
        await mark_deleted(self.db, row)
        bindings = (
            (await self.db.execute(select(LibraryWordBinding).where(LibraryWordBinding.library_id == library_id, not_deleted(LibraryWordBinding))))
            .scalars()
            .all()
        )
        for b in bindings:
            await mark_deleted(self.db, b)
        scan_bindings = (
            (
                await self.db.execute(
                    select(ComplianceLibraryBinding).where(
                        ComplianceLibraryBinding.library_id == library_id,
                        not_deleted(ComplianceLibraryBinding),
                    )
                )
            )
            .scalars()
            .all()
        )
        for b in scan_bindings:
            await mark_deleted(self.db, b)

    async def get_library_or_raise(self, library_id: UUID) -> WordLibrary:
        """加载词库并校验租户权限。"""
        row = await self.db.get(WordLibrary, library_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("词库不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def ensure_default_library(self) -> WordLibraryOut:
        """确保租户存在默认词库（种子/迁移）。"""
        existing = (
            await self.db.execute(
                select(WordLibrary).where(
                    WordLibrary.tenant_id == self.ctx.tenant_id,
                    WordLibrary.name == DEFAULT_WORD_LIBRARY_NAME,
                    not_deleted(WordLibrary),
                )
            )
        ).scalar_one_or_none()
        if existing:
            return await self.library_out(existing)
        return await self.create_library(WordLibraryCreate(name=DEFAULT_WORD_LIBRARY_NAME, description="系统迁移/种子默认词库"))
