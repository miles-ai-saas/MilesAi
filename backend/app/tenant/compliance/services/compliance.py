"""敏感词库与入出站合规扫描（智能体对话等路径调用 CompliancePipeline）。

Agent.chat 在推理前后调用 check_input / check_output；BLOCK 抛 BadRequestError 并写 InterceptLog。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.tenant.compliance.models import InterceptLog, SensitiveAction, SensitiveWord
from app.common.schema import PageParams, PageResult
from app.tenant.compliance.schemas.compliance import (
    ComplianceScanMatch,
    ComplianceScanRequest,
    ComplianceScanResult,
    InterceptLogOut,
    SensitiveWordBatchCreate,
    SensitiveWordCreate,
    SensitiveWordOut,
    SensitiveWordUpdate,
)
from app.core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService
from app.tenant.compliance.services.pipeline import CompliancePipeline


class ComplianceService(BaseService):
    """敏感词 CRUD、试跑 scan、拦截审计日志。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def _pipeline(self) -> CompliancePipeline:
        """按租户加载活跃敏感词构建扫描器。"""
        filters = tenant_filters(self.ctx, SensitiveWord.tenant_id)
        stmt = select(SensitiveWord).where(
            SensitiveWord.is_active.is_(True),
            not_deleted(SensitiveWord),
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
        """用户入站文本；命中 BLOCK 时抛 BadRequestError。"""
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
        """模型出站文本；BLOCK 时同样拦截并记审计。"""
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
        filters = append_not_deleted(tenant_filters(self.ctx, SensitiveWord.tenant_id), SensitiveWord)
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

    async def scan_text(self, body: ComplianceScanRequest) -> ComplianceScanResult:
        """管理端试跑：返回 blocked/warned，命中时写 InterceptLog 但不抛错。"""
        result = (await self._pipeline()).scan(body.text)
        matches = [
            ComplianceScanMatch(word=m.word, action=m.action) for m in result.matches
        ]
        if result.has_block:
            first = result.matches[0]
            await self._log_intercept(
                module=body.module,
                direction="in",
                matched_word=first.word,
                action=first.action,
                content=body.text,
            )
        elif result.has_warn:
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
        )

    async def update_word(self, word_id: UUID, body: SensitiveWordUpdate) -> SensitiveWordOut:
        row = await self.db.get(SensitiveWord, word_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("敏感词不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        await self.db.flush()
        await self.db.refresh(row)
        return SensitiveWordOut.model_validate(row)

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

    async def batch_create_words(self, body: SensitiveWordBatchCreate) -> list[SensitiveWordOut]:
        out: list[SensitiveWordOut] = []
        for item in body.words:
            row = SensitiveWord(
                tenant_id=self.ctx.tenant_id,
                word=item.word.strip(),
                category=item.category,
                action=item.action,
            )
            self.db.add(row)
            await self.db.flush()
            await self.db.refresh(row)
            out.append(SensitiveWordOut.model_validate(row))
        return out

    async def delete_word(self, word_id: UUID) -> None:
        row = await self.db.get(SensitiveWord, word_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("敏感词不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        await mark_deleted(self.db, row)

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
