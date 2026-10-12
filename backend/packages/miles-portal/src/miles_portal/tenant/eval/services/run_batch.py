"""评测批跑：逐 case 调用 AgentService.chat 并打分。"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from miles_common.trace import get_trace_id
from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.models.agent import Agent
from miles_core.models.agent.chat_call import AgentChatCall
from miles_core.models.eval import EvalCase, EvalRun, EvalRunItem, EvalRunStatus
from miles_core.models.platform.user import User
from miles_core.soft_delete import is_marked_deleted
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.schemas.agent import ChatRequest
from miles_portal.tenant.agents.services.agent import AgentService
from miles_portal.tenant.eval.services.scoring import score_case
from miles_portal.tenant.models.services.model_resolve import resolve_model_for_invoke

logger = get_logger(__name__)


async def run_eval_batch_async(run_id: UUID) -> None:
    """执行一整次 EvalRun（由 Celery 任务调用）。"""
    async with AsyncSessionLocal() as db:
        run = await db.get(EvalRun, run_id)
        if not run:
            logger.warning("eval run missing: %s", run_id)
            return
        if run.status == EvalRunStatus.RUNNING.value:
            logger.warning("eval run already running: %s", run_id)
            return
        if not run.created_by:
            run.status = EvalRunStatus.FAILED.value
            run.finished_at = datetime.now(UTC)
            run.error_message = "缺少 created_by，无法以用户身份执行 chat"
            await db.commit()
            return

        run.status = EvalRunStatus.RUNNING.value
        run.started_at = datetime.now(UTC)
        run.error_message = None
        await db.commit()

        agent = (
            await db.execute(
                select(Agent).where(Agent.id == run.agent_id).options(selectinload(Agent.model_config))
            )
        ).scalar_one_or_none()
        if not agent or is_marked_deleted(agent):
            run = await db.get(EvalRun, run_id)
            assert run is not None
            run.status = EvalRunStatus.FAILED.value
            run.finished_at = datetime.now(UTC)
            run.error_message = "智能体不存在或已删除"
            await db.commit()
            return

        user = await db.get(User, run.created_by)
        ctx = TenantContext(
            user_id=run.created_by,
            tenant_id=run.tenant_id,
            username=user.username if user else "eval",
            is_superuser=False,
            permissions=frozenset(["agent:read", "agent:write"]),
        )

        judge_model = None
        if run.scoring_mode in ("auto", "llm_judge"):
            opts = run.options if isinstance(run.options, dict) else {}
            raw_judge_id = opts.get("judge_model_config_id")
            try:
                if raw_judge_id:
                    from miles_core.models.model import ModelConfig
                    from miles_portal.tenant.models.services.model_resolve import resolve_model_by_id

                    judge_cfg = await db.get(ModelConfig, UUID(str(raw_judge_id)))
                    if judge_cfg is not None and not is_marked_deleted(judge_cfg):
                        judge_model = await resolve_model_by_id(db, judge_cfg.id, run.tenant_id)
                elif agent.model_config is not None:
                    judge_model = await resolve_model_for_invoke(db, agent.model_config, run.tenant_id)
            except Exception:
                judge_model = None

        items = list(
            (
                await db.execute(
                    select(EvalRunItem)
                    .where(EvalRunItem.run_id == run.id)
                    .order_by(EvalRunItem.created_at.asc())
                )
            ).scalars().all()
        )

        passed_n = failed_n = errored_n = skipped_n = 0
        for item in items:
            case = await db.get(EvalCase, item.case_id)
            if not case:
                item.status = "error"
                item.error_message = "用例不存在"
                errored_n += 1
                await db.commit()
                continue

            conv_id = f"eval:{run.id}:{case.id}"
            item.status = "running"
            await db.commit()

            t0 = time.perf_counter()
            try:
                svc = AgentService(db, ctx)
                resp = await svc.chat(
                    run.agent_id,
                    ChatRequest(query=case.query, conversation_id=conv_id),
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                answer = resp.answer or ""
                item.answer_preview = answer[:500]
                item.latency_ms = latency_ms
                item.trace_id = get_trace_id()
                item.error_message = None

                call = (
                    await db.execute(
                        select(AgentChatCall)
                        .where(
                            AgentChatCall.tenant_id == run.tenant_id,
                            AgentChatCall.agent_id == run.agent_id,
                            AgentChatCall.conversation_id == conv_id,
                        )
                        .order_by(AgentChatCall.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if call:
                    item.call_id = call.id
                    if call.trace_id:
                        item.trace_id = call.trace_id
                    item.latency_ms = call.latency_ms or latency_ms

                score, passed, detail = await score_case(
                    answer=answer,
                    query=case.query,
                    expected=case.expected,
                    scoring_mode=run.scoring_mode,
                    model=judge_model,
                )
                item.score = score
                item.passed = passed
                item.score_detail = detail
                item.status = "success"
                if passed is True:
                    passed_n += 1
                elif passed is False:
                    failed_n += 1
                else:
                    skipped_n += 1
            except Exception as exc:
                item.status = "error"
                item.latency_ms = int((time.perf_counter() - t0) * 1000)
                item.error_message = str(exc)[:2000]
                item.score_detail = {"method": "error"}
                errored_n += 1
                logger.exception("eval case failed run=%s case=%s", run.id, case.id)
            await db.commit()

        # 刷新 run 状态
        run = await db.get(EvalRun, run_id)
        assert run is not None
        run.status = EvalRunStatus.SUCCESS.value if errored_n == 0 else EvalRunStatus.FAILED.value
        run.finished_at = datetime.now(UTC)
        run.summary = {
            "total": len(items),
            "passed": passed_n,
            "failed": failed_n,
            "errored": errored_n,
            "unscored": skipped_n,
        }
        if errored_n and not passed_n and not failed_n:
            run.error_message = f"{errored_n} 条用例执行失败"
        await db.commit()
