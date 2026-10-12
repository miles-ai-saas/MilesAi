"""A2A Server：``tasks/get`` / ``tasks/cancel`` 与产物下载。

经 ``server`` 门面 re-export；``get_generative_job_for_tenant`` / ``AttachmentService``
等经 ``server`` 模块属性解析，保持单测 monkeypatch 路径稳定。
"""

from __future__ import annotations

import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import AppError, BadRequestError, ForbiddenError, NotFoundError
from miles_core.models.model.generative_job import GenerativeJob
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a.server import (
    AUDIT_ACTION_ARTIFACT_DOWNLOAD,
    AUDIT_OUTCOME_FAILED,
    AUDIT_OUTCOME_OK,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    TASK_NOT_CANCELABLE,
    TASK_NOT_FOUND,
    artifact_ids_from_job_result,
    build_a2a_artifacts,
    build_a2a_task,
    jsonrpc_error,
    jsonrpc_result,
    progress_text,
    timestamp_iso,
    to_a2a_task_state,
)
from miles_portal.tenant.a2a.services import streaming


def parse_task_id(params: dict) -> UUID:
    """取 ``tasks/*`` 的 ``params.id`` 并解析为 UUID；非法一律 ``BadRequestError``。"""
    raw = params.get("id")
    if not isinstance(raw, str) or not raw.strip():
        raise BadRequestError("tasks/* 缺少 params.id")
    try:
        return UUID(raw.strip())
    except ValueError as exc:
        raise BadRequestError("params.id 不是合法的任务 ID") from exc


async def load_owned_agent_task(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    task_id: UUID,
) -> GenerativeJob:
    """取「该智能体自己发起」的生成任务；不存在或不属于它一律 ``NotFoundError``。

    必须校验归属：只按租户取数会让同租户另一个智能体的 key 也能查/取消本智能体任务，
    并据 ``task_id`` 推断其产物下载地址。回 404 而非 403 —— 不向对端确认任务是否存在。

    外租户 id 由下层 ``get_generative_job_for_tenant`` 的 ``ForbiddenError`` 表达，此处
    一并归一为 ``NotFoundError``：A2A 对外面不接受以 403 区分「存在但越权」与「不存在」。
    """
    from miles_portal.tenant.a2a.services import server as svc

    try:
        job = await svc.get_generative_job_for_tenant(db, ctx, task_id)
    except ForbiddenError:
        # 外租户 id：下层 ``assert_tenant_access`` 抛 403。若让它逸出，对端会拿到平台信封的
        # HTTP 403 —— 既破坏本端点「协议级错误一律回 JSON-RPC 信封」的契约（对端无从把错误
        # 对回自己的 ``id``），又让 403 与 ``-32001`` 可区分，等于给出探测「该任务是否存在于
        # 别的租户」的 oracle。故与「不属于本智能体」同口径归一；文案固定，不回显内部措辞。
        raise NotFoundError("生成任务不存在") from None
    if job.source_ref_type != "agent" or job.source_ref_id != agent_id:
        raise NotFoundError("生成任务不存在")
    return job


async def read_task_artifact(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    task_id: UUID,
    attachment_id: UUID,
) -> tuple[bytes, str, str]:
    """下载某任务产物，返回 ``(data, mime_type, filename)``。

    授权精确到「该智能体 · 该任务 · 该产物」：先验任务归属，再验附件确为该任务产物，
    否则本租户任意附件都能被取走。成败都留一条审计流水（「谁把产物取走了」要查得到）；
    跨租户附件对外归一为「附件不存在」（404），不确认存在性。
    """
    from miles_portal.tenant.a2a.services import server as svc

    started = time.monotonic()
    try:
        job = await svc.load_owned_agent_task(db, ctx, agent_id, task_id)
        if str(attachment_id) not in artifact_ids_from_job_result(job.result):
            raise NotFoundError("附件不是该任务的产物")
        data, mime, filename = await svc.AttachmentService(db, ctx).read_attachment_bytes(attachment_id)
    except NotFoundError:
        # 含 load_owned_agent_task 的各种「不存在」与「非本任务产物」
        await svc._audit_artifact_failure(ctx, agent_id, task_id, started, TASK_NOT_FOUND)
        raise
    except ForbiddenError as exc:
        # 跨租户附件：与「非本任务产物」同口径回 404，不向对端确认存在性。归一放在 A2A
        # 对外面而非 AttachmentService —— 后者对内部调用方（工作台附件列表等）是对的。
        await svc._audit_artifact_failure(ctx, agent_id, task_id, started, TASK_NOT_FOUND, origin=exc)
        raise NotFoundError("附件不存在") from None
    except AppError as exc:
        # 如「附件文件未就绪」（400）。状态码由全局处理器给，此处只补留痕。
        await svc._audit_artifact_failure(ctx, agent_id, task_id, started, INVALID_PARAMS, origin=exc)
        raise
    except Exception:
        # 存储 / DB 故障：留痕后原样重抛 → HTTP 500 平台信封（与 RPC 层口径一致）。
        await svc._audit_artifact_failure(ctx, agent_id, task_id, started, INTERNAL_ERROR)
        raise
    await svc.write_a2a_audit(
        ctx=ctx,
        agent_id=agent_id,
        action=AUDIT_ACTION_ARTIFACT_DOWNLOAD,
        outcome=AUDIT_OUTCOME_OK,
        detail={"taskId": str(task_id), "durationMs": streaming.elapsed_ms(started)},
    )
    return data, mime, filename


async def _audit_artifact_failure(
    ctx: TenantContext,
    agent_id: UUID,
    task_id: UUID,
    started: float,
    error_code: int,
    *,
    origin: AppError | None = None,
) -> None:
    """产物下载失败留痕：越权尝试与存储故障都是排查线索，不能只在成功时记。

    ``origin`` 非空时额外记原始异常类型与 HTTP status —— 对外的 ``errorCode`` 已被压平
    （跨租户与「非本任务产物」都回 ``TASK_NOT_FOUND``），这是租户可见面上唯一能读出真实
    原因的出口。只记类型与状态码，不记 message。
    """
    from miles_portal.tenant.a2a.services import server as svc

    detail: dict = {"taskId": str(task_id), "errorCode": error_code, "durationMs": streaming.elapsed_ms(started)}
    if origin is not None:
        detail["errorType"] = type(origin).__name__
        detail["errorStatus"] = origin.status_code
    await svc.write_a2a_audit(
        ctx=ctx,
        agent_id=agent_id,
        action=AUDIT_ACTION_ARTIFACT_DOWNLOAD,
        outcome=AUDIT_OUTCOME_FAILED,
        detail=detail,
    )


async def _handle_tasks_get(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    req_id: object,
    params: dict,
    *,
    base_url: str,
) -> dict:
    """``tasks/get``：查生成任务状态，成功时附产物下载地址。

    只读查询走 ORM 取数（不经 ``GenerativeJobService.get_job``，后者会回写会话
    artifacts —— 对外查询不应带写副作用）。
    """
    from miles_portal.tenant.a2a.services import server as svc

    try:
        job_id = svc.parse_task_id(params)
        job = await svc.load_owned_agent_task(db, ctx, agent_id, job_id)
    except BadRequestError as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    except NotFoundError as exc:
        return jsonrpc_error(req_id, TASK_NOT_FOUND, str(exc))

    return jsonrpc_result(
        req_id,
        build_a2a_task(
            task_id=str(job.id),
            context_id=svc.context_id_from_job_params(job.params),
            state=to_a2a_task_state(job.status.value),
            timestamp=timestamp_iso(job.updated_at),
            artifacts=build_a2a_artifacts(job_result=job.result, agent_id=agent_id, task_id=job.id, base_url=base_url),
            text=progress_text(progress_message=job.progress_message, percent=job.progress_percent),
            percent=job.progress_percent,
        ),
    )


async def _handle_tasks_cancel(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    req_id: object,
    params: dict,
) -> dict:
    """``tasks/cancel``：取消未结束的生成任务；已结束回 ``TASK_NOT_CANCELABLE``。"""
    from miles_portal.tenant.a2a.services import server as svc

    try:
        job_id = svc.parse_task_id(params)
        await svc.load_owned_agent_task(db, ctx, agent_id, job_id)
    except BadRequestError as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    except NotFoundError as exc:
        return jsonrpc_error(req_id, TASK_NOT_FOUND, str(exc))

    try:
        job = await svc.GenerativeJobService(db, ctx).cancel_job(job_id)
    except BadRequestError as exc:
        return jsonrpc_error(req_id, TASK_NOT_CANCELABLE, str(exc))

    return jsonrpc_result(
        req_id,
        build_a2a_task(
            task_id=str(job.id),
            context_id=svc.context_id_from_job_params(job.params),
            state=to_a2a_task_state(job.status.value),
            timestamp=timestamp_iso(job.updated_at),
            text=progress_text(progress_message=job.progress_message, percent=job.progress_percent),
            percent=job.progress_percent,
        ),
    )
