"""入出站敏感词检测、媒体审核与试跑扫描。

Agent 对话链：``AgentChatMixin.chat`` → ``check_input`` / ``check_media_input`` / ``check_output``；
画布 ``ComplianceCheck`` 节点走 ``CompliancePipeline`` 但不写 InterceptLog。
"""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from miles_common.exceptions import BadRequestError
from miles_common.schemas.media import MediaRefIn
from miles_portal.tenant.compliance.models import InterceptLog, SensitiveAction
from miles_portal.tenant.compliance.schemas.compliance import (
    ComplianceScanMatch,
    ComplianceScanRequest,
    ComplianceScanResult,
)
from miles_portal.tenant.compliance.services.compliance.media_audit import (
    DEFAULT_MAX_MEDIA_AUDIT,
    check_media_safety,
)
from miles_portal.tenant.compliance.services.pipeline import CompliancePipeline
from miles_portal.tenant.compliance.services.word_resolve import load_tenant_scan_words


class ComplianceInterceptMixin:
    """入出站敏感词检测、入站图片视觉审核、试跑扫描与拦截日志写入。"""

    async def compliance_pipeline(self) -> CompliancePipeline | None:
        """按租户已绑定词库构建扫描 Pipeline；无词时返回 None。"""
        words = await load_tenant_scan_words(self.db, self.ctx.tenant_id)
        if not words:
            return None
        return CompliancePipeline(words)

    async def log_intercept(
        self,
        *,
        module: str,
        direction: str,
        matched_word: str | None,
        action: SensitiveAction,
        content: str,
    ) -> None:
        """写入一条敏感词拦截审计记录。"""
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
        """入站文本扫描；命中 block 时抛 ``BadRequestError``。"""
        pipeline = await self.compliance_pipeline()
        if pipeline is None:
            return text
        result = pipeline.scan(text)
        if result.matches:
            first = result.matches[0]
            await self.log_intercept(
                module=module,
                direction="in",
                matched_word=first.word,
                action=result.worst_action or first.action or SensitiveAction.WARN,
                content=text,
            )
            if result.has_block:
                raise BadRequestError(f"输入内容包含敏感词，已拦截：{first.word}")
        return text

    async def check_media_input(
        self,
        media: Sequence[MediaRefIn] | Sequence[UUID] | None,
        *,
        module: str,
        max_images: int = DEFAULT_MAX_MEDIA_AUDIT,
    ) -> None:
        """入站附图视觉审核；``safe=False`` 记拦截日志并抛 ``BadRequestError``。

        仅审核图片；音/视频跳过。无 Vision/LLM 或调用失败 fail-open。
        同一请求最多审核 ``max_images`` 张（默认 5）。
        """
        if not media:
            return
        ids: list[UUID] = []
        for item in media:
            if isinstance(item, UUID):
                ids.append(item)
            else:
                aid = getattr(item, "attachment_id", None)
                if aid is not None:
                    ids.append(aid if isinstance(aid, UUID) else UUID(str(aid)))
        if not ids:
            return

        audited = 0
        limit = max(0, int(max_images))
        for aid in ids:
            if audited >= limit:
                break
            result = await check_media_safety(aid, self.db, self.ctx)
            reason = str(result.get("reason") or "")
            # 非图片跳过；无模型则整批放行（避免对每张图重复探测）
            if result.get("category") == "none" and result.get("safe", True):
                if "非图片" in reason:
                    continue
                if "无可用模型" in reason:
                    return
            audited += 1
            if result.get("safe", True):
                continue
            category = str(result.get("category") or "违规")[:128]
            snippet = f"[media:{aid}] {category}: {reason[:400]}"
            await self.log_intercept(
                module=module,
                direction="in",
                matched_word=category,
                action=SensitiveAction.BLOCK,
                content=snippet,
            )
            detail = f"（{reason}）" if reason else ""
            raise BadRequestError(f"附图未通过内容安全审核，已拦截：{category}{detail}")

    async def check_output(self, text: str, *, module: str) -> str:
        """出站文本扫描；命中 block 时抛 ``BadRequestError``。"""
        pipeline = await self.compliance_pipeline()
        if pipeline is None:
            return text
        result = pipeline.scan(text)
        if result.matches:
            first = result.matches[0]
            await self.log_intercept(
                module=module,
                direction="out",
                matched_word=first.word,
                action=result.worst_action or first.action or SensitiveAction.WARN,
                content=text,
            )
            if result.has_block:
                raise BadRequestError(f"输出内容包含敏感词，已拦截：{first.word}")
        return text

    async def scan_text(self, body: ComplianceScanRequest) -> ComplianceScanResult:
        """管理端试跑扫描，返回命中列表与是否拦截/警告。"""
        pipeline = await self.compliance_pipeline()
        if pipeline is None:
            return ComplianceScanResult(blocked=False, warned=False, matches=[], scanning_enabled=False)
        result = pipeline.scan(body.text)
        matches = [ComplianceScanMatch(word=m.word, action=m.action) for m in result.matches]
        if result.has_block and result.matches:
            first = result.matches[0]
            await self.log_intercept(
                module=body.module,
                direction="in",
                matched_word=first.word,
                action=first.action,
                content=body.text,
            )
        elif result.has_warn and result.matches:
            first = result.matches[0]
            await self.log_intercept(
                module=body.module,
                direction="in",
                matched_word=first.word,
                action=SensitiveAction.WARN,
                content=body.text,
            )
        return ComplianceScanResult(blocked=result.has_block, warned=result.has_warn, matches=matches, scanning_enabled=True)
