"""合规：词库/词条 CRUD、租户扫描绑定、入出站检测与拦截日志。"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.tenant.compliance.models import (
    COMPLIANCE_SCOPE_TENANT,
    DEFAULT_WORD_LIBRARY_NAME,
    ComplianceLibraryBinding,
    InterceptLog,
    LibraryWordBinding,
    SensitiveAction,
    SensitiveWordEntry,
    WordLibrary,
)
from app.common.schema import PageParams, PageResult
from app.tenant.compliance.schemas.compliance import (
    ComplianceScanBindingsOut,
    ComplianceScanBindingsUpdate,
    ComplianceScanMatch,
    ComplianceScanRequest,
    ComplianceScanResult,
    EntryLibrariesUpdate,
    EntryLibraryRef,
    InterceptLogOut,
    LibraryWordBatchCreate,
    LibraryWordCreate,
    LibraryWordOut,
    LibraryWordUpdate,
    SensitiveWordEntryOut,
    WordLibraryCreate,
    WordLibraryOut,
    WordLibraryUpdate,
)
from app.core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService
from app.tenant.compliance.services.pipeline import CompliancePipeline
from app.tenant.compliance.services.word_resolve import (
    get_or_create_entry,
    load_tenant_scan_words,
)


class ComplianceService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def _pipeline(self) -> CompliancePipeline | None:
        words = await load_tenant_scan_words(self.db, self.ctx.tenant_id)
        if not words:
            return None
        return CompliancePipeline(words)

    async def _log_intercept(
        self,
        *,
        module: str,
        direction: str,
        matched_word: str | None,
        action: SensitiveAction,
        content: str,
    ) -> None:
        snippet = content[:500] if content else None
        self.db.add(
            InterceptLog(
                tenant_id=self.ctx.tenant_id,
                user_id=self.ctx.user_id,
                module=module,
                direction=direction,
                matched_word=matched_word,
                action=action,
                content_snippet=snippet,
            )
        )

    async def check_input(self, text: str, *, module: str) -> str:
        pipeline = await self._pipeline()
        if pipeline is None:
            return text
        result = pipeline.scan(text)
        if result.matches:
            first = result.matches[0]
            await self._log_intercept(
                module=module,
                direction="in",
                matched_word=first.word,
                action=first.worst_action or SensitiveAction.WARN,
                content=text,
            )
            if result.has_block:
                raise BadRequestError(f"输入内容包含敏感词，已拦截：{first.word}")
        return text

    async def check_output(self, text: str, *, module: str) -> str:
        pipeline = await self._pipeline()
        if pipeline is None:
            return text
        result = pipeline.scan(text)
        if result.matches:
            first = result.matches[0]
            await self._log_intercept(
                module=module,
                direction="out",
                matched_word=first.word,
                action=first.worst_action or SensitiveAction.WARN,
                content=text,
            )
            if result.has_block:
                raise BadRequestError(f"输出内容包含敏感词，已拦截：{first.word}")
        return text

    # --- 扫描绑定 ---

    async def get_scan_bindings(self) -> ComplianceScanBindingsOut:
        libs = await self._list_libraries_query(active_only=False)
        bound_ids = set(
            (
                await self.db.execute(
                    select(ComplianceLibraryBinding.library_id).where(
                        ComplianceLibraryBinding.tenant_id == self.ctx.tenant_id,
                        ComplianceLibraryBinding.scope == COMPLIANCE_SCOPE_TENANT,
                        not_deleted(ComplianceLibraryBinding),
                    )
                )
            ).scalars().all()
        )
        out_libs = [await self._library_out(lib) for lib in libs]
        return ComplianceScanBindingsOut(
            library_ids=list(bound_ids),
            libraries=out_libs,
        )

    async def set_scan_bindings(self, body: ComplianceScanBindingsUpdate) -> ComplianceScanBindingsOut:
        wanted = set(body.library_ids)
        if wanted:
            found = (
                await self.db.execute(
                    select(WordLibrary.id).where(
                        WordLibrary.id.in_(wanted),
                        WordLibrary.tenant_id == self.ctx.tenant_id,
                        not_deleted(WordLibrary),
                    )
                )
            ).scalars().all()
            if len(found) != len(wanted):
                raise BadRequestError("部分词库不存在或无权访问")

        existing = (
            await self.db.execute(
                select(ComplianceLibraryBinding).where(
                    ComplianceLibraryBinding.tenant_id == self.ctx.tenant_id,
                    ComplianceLibraryBinding.scope == COMPLIANCE_SCOPE_TENANT,
                    not_deleted(ComplianceLibraryBinding),
                )
            )
        ).scalars().all()
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

    # --- 词库 ---

    async def _count_words_in_library(self, library_id: UUID) -> int:
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

    async def _library_out(self, lib: WordLibrary) -> WordLibraryOut:
        count = await self._count_words_in_library(lib.id)
        data = WordLibraryOut.model_validate(lib)
        return data.model_copy(update={"word_count": count})

    async def _list_libraries_query(self, *, active_only: bool) -> list[WordLibrary]:
        filters = append_not_deleted(tenant_filters(self.ctx, WordLibrary.tenant_id), WordLibrary)
        if active_only:
            filters.append(WordLibrary.is_active.is_(True))
        stmt = select(WordLibrary).where(*filters).order_by(
            WordLibrary.sort_order.asc(), WordLibrary.created_at.desc()
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_libraries(self, params: PageParams) -> PageResult[WordLibraryOut]:
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
            items=[await self._library_out(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_library(self, body: WordLibraryCreate) -> WordLibraryOut:
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
        return await self._library_out(row)

    async def get_library(self, library_id: UUID) -> WordLibraryOut:
        row = await self._get_library_or_raise(library_id)
        return await self._library_out(row)

    async def update_library(self, library_id: UUID, body: WordLibraryUpdate) -> WordLibraryOut:
        row = await self._get_library_or_raise(library_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            if k == "name" and v is not None:
                setattr(row, k, v.strip())
            else:
                setattr(row, k, v)
        await self.db.flush()
        await self.db.refresh(row)
        return await self._library_out(row)

    async def delete_library(self, library_id: UUID) -> None:
        row = await self._get_library_or_raise(library_id)
        await mark_deleted(self.db, row)
        bindings = (
            await self.db.execute(
                select(LibraryWordBinding).where(
                    LibraryWordBinding.library_id == library_id,
                    not_deleted(LibraryWordBinding),
                )
            )
        ).scalars().all()
        for b in bindings:
            await mark_deleted(self.db, b)
        scan_bindings = (
            await self.db.execute(
                select(ComplianceLibraryBinding).where(
                    ComplianceLibraryBinding.library_id == library_id,
                    not_deleted(ComplianceLibraryBinding),
                )
            )
        ).scalars().all()
        for b in scan_bindings:
            await mark_deleted(self.db, b)

    async def _get_library_or_raise(self, library_id: UUID) -> WordLibrary:
        row = await self.db.get(WordLibrary, library_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("词库不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    # --- 库内词条 ---

    async def _binding_out(self, binding: LibraryWordBinding, word: str) -> LibraryWordOut:
        return LibraryWordOut(
            id=binding.id,
            library_id=binding.library_id,
            entry_id=binding.entry_id,
            word=word,
            action=binding.action,
            is_active=binding.is_active,
            created_at=binding.created_at,
        )

    async def list_library_words(
        self, library_id: UUID, params: PageParams
    ) -> PageResult[LibraryWordOut]:
        await self._get_library_or_raise(library_id)
        filters = [
            LibraryWordBinding.library_id == library_id,
            not_deleted(LibraryWordBinding),
            not_deleted(SensitiveWordEntry),
        ]
        total = await self.db.scalar(
            select(func.count())
            .select_from(LibraryWordBinding)
            .join(SensitiveWordEntry, SensitiveWordEntry.id == LibraryWordBinding.entry_id)
            .where(*filters)
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
            items=[await self._binding_out(b, w) for b, w in rows],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def add_library_word(self, library_id: UUID, body: LibraryWordCreate) -> LibraryWordOut:
        lib = await self._get_library_or_raise(library_id)
        entry = await get_or_create_entry(
            self.db, tenant_id=lib.tenant_id, word=body.word
        )
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
        binding = LibraryWordBinding(
            library_id=library_id,
            entry_id=entry.id,
            action=body.action,
            is_active=body.is_active,
        )
        self.db.add(binding)
        await self.db.flush()
        await self.db.refresh(binding)
        return await self._binding_out(binding, entry.word)

    async def batch_add_library_words(
        self, library_id: UUID, body: LibraryWordBatchCreate
    ) -> list[LibraryWordOut]:
        out: list[LibraryWordOut] = []
        for item in body.words:
            try:
                out.append(await self.add_library_word(library_id, item))
            except BadRequestError:
                continue
        return out

    async def update_library_word(
        self, library_id: UUID, binding_id: UUID, body: LibraryWordUpdate
    ) -> LibraryWordOut:
        await self._get_library_or_raise(library_id)
        binding = await self._get_binding_or_raise(binding_id, library_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(binding, k, v)
        await self.db.flush()
        entry = await self.db.get(SensitiveWordEntry, binding.entry_id)
        return await self._binding_out(binding, entry.word if entry else "")

    async def delete_library_word(self, library_id: UUID, binding_id: UUID) -> None:
        await self._get_library_or_raise(library_id)
        binding = await self._get_binding_or_raise(binding_id, library_id)
        await mark_deleted(self.db, binding)

    async def _get_binding_or_raise(
        self, binding_id: UUID, library_id: UUID
    ) -> LibraryWordBinding:
        row = await self.db.get(LibraryWordBinding, binding_id)
        if not row or is_marked_deleted(row) or row.library_id != library_id:
            raise NotFoundError("词条关联不存在")
        lib = await self.db.get(WordLibrary, library_id)
        if lib:
            assert_tenant_access(self.ctx, lib.tenant_id)
        return row

    # --- 词条（租户级，含多库） ---

    async def get_entry(self, entry_id: UUID) -> SensitiveWordEntryOut:
        entry = await self._get_entry_or_raise(entry_id)
        return await self._entry_out(entry)

    async def set_entry_libraries(
        self, entry_id: UUID, body: EntryLibrariesUpdate
    ) -> SensitiveWordEntryOut:
        entry = await self._get_entry_or_raise(entry_id)
        wanted = set(body.library_ids)
        if wanted:
            found = (
                await self.db.execute(
                    select(WordLibrary.id).where(
                        WordLibrary.id.in_(wanted),
                        WordLibrary.tenant_id == entry.tenant_id,
                        not_deleted(WordLibrary),
                    )
                )
            ).scalars().all()
            if len(found) != len(wanted):
                raise BadRequestError("部分词库不存在")

        existing = (
            await self.db.execute(
                select(LibraryWordBinding).where(
                    LibraryWordBinding.entry_id == entry_id,
                    not_deleted(LibraryWordBinding),
                )
            )
        ).scalars().all()
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
        return await self._entry_out(entry)

    async def _get_entry_or_raise(self, entry_id: UUID) -> SensitiveWordEntry:
        row = await self.db.get(SensitiveWordEntry, entry_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("词条不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def _entry_out(self, entry: SensitiveWordEntry) -> SensitiveWordEntryOut:
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

    # --- 扫描试跑 / 日志 ---

    async def scan_text(self, body: ComplianceScanRequest) -> ComplianceScanResult:
        pipeline = await self._pipeline()
        if pipeline is None:
            return ComplianceScanResult(
                blocked=False,
                warned=False,
                matches=[],
                scanning_enabled=False,
            )
        result = pipeline.scan(body.text)
        matches = [ComplianceScanMatch(word=m.word, action=m.action) for m in result.matches]
        if result.has_block and result.matches:
            first = result.matches[0]
            await self._log_intercept(
                module=body.module,
                direction="in",
                matched_word=first.word,
                action=first.action,
                content=body.text,
            )
        elif result.has_warn and result.matches:
            first = result.matches[0]
            await self._log_intercept(
                module=body.module,
                direction="in",
                matched_word=first.word,
                action=SensitiveAction.WARN,
                content=body.text,
            )
        return ComplianceScanResult(
            blocked=result.has_block,
            warned=result.has_warn,
            matches=matches,
            scanning_enabled=True,
        )

    async def list_logs(self, params: PageParams) -> PageResult[InterceptLogOut]:
        filters = tenant_filters(self.ctx, InterceptLog.tenant_id)
        total = await self.db.scalar(
            select(func.count()).select_from(InterceptLog).where(*filters)
        )
        stmt = (
            select(InterceptLog)
            .where(*filters)
            .order_by(InterceptLog.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[InterceptLogOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def ensure_default_library(self) -> WordLibraryOut:
        """种子/迁移后：确保租户有默认词库（不自动绑定扫描）。"""
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
            return await self._library_out(existing)
        return await self.create_library(
            WordLibraryCreate(name=DEFAULT_WORD_LIBRARY_NAME, description="系统迁移/种子默认词库")
        )
