from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.app_tenant.compliance.models import InterceptLog, SensitiveAction, SensitiveWord
from app.common.schema import PageParams, PageResult
from app.app_tenant.compliance.schemas.compliance import (
    InterceptLogOut,
    SensitiveWordCreate,
    SensitiveWordOut,
)
from app.core.service import BaseService
from app.app_tenant.compliance.services.pipeline import CompliancePipeline


class ComplianceService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def _pipeline(self) -> CompliancePipeline:
        filters = tenant_filters(self.ctx, SensitiveWord.tenant_id)
        stmt = select(SensitiveWord).where(
            SensitiveWord.is_active.is_(True),
            *filters,
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        words = [(r.word, r.action) for r in rows]
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
        log = InterceptLog(
            tenant_id=self.ctx.tenant_id,
            user_id=self.ctx.user_id,
            module=module,
            direction=direction,
            matched_word=matched_word,
            action=action,
            content_snippet=snippet,
        )
        self.db.add(log)

    async def check_input(self, text: str, *, module: str) -> str:
        result = (await self._pipeline()).scan(text)
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
        result = (await self._pipeline()).scan(text)
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

    async def list_words(self, params: PageParams) -> PageResult[SensitiveWordOut]:
        filters = tenant_filters(self.ctx, SensitiveWord.tenant_id)
        total = await self.db.scalar(
            select(func.count()).select_from(SensitiveWord).where(*filters)
        )
        stmt = (
            select(SensitiveWord)
            .where(*filters)
            .order_by(SensitiveWord.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[SensitiveWordOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_word(self, body: SensitiveWordCreate) -> SensitiveWordOut:
        row = SensitiveWord(
            tenant_id=self.ctx.tenant_id,
            word=body.word.strip(),
            category=body.category,
            action=body.action,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return SensitiveWordOut.model_validate(row)

    async def delete_word(self, word_id: UUID) -> None:
        row = await self.db.get(SensitiveWord, word_id)
        if not row:
            raise NotFoundError("敏感词不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        await self.db.delete(row)

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
