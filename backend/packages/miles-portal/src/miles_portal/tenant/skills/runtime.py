"""技能包运行时：读取 reference、执行 scripts（供内置工具与 tool_agent 调用）。"""

from __future__ import annotations

import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.config import get_settings
from miles_core.soft_delete import is_marked_deleted
from miles_core.tenant import TenantContext, assert_tenant_access
from miles_exec.sandbox.validate import validate_script_source
from miles_portal.tenant.skills.models import SkillPackage
from miles_portal.tenant.skills.skill_layout import read_skill_resource, read_skill_script_source


async def resolve_bound_skill(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    skill_package_id: UUID | str | None,
    skill_slug: str | None = None,
) -> SkillPackage:
    """解析绑定的技能包：优先按 ID，其次按 slug；不存在或已停用抛 ``NotFoundError``。"""
    if not skill_package_id and not skill_slug:
        raise BadRequestError("未指定技能包")
    row: SkillPackage | None = None
    if skill_package_id:
        try:
            sid = UUID(str(skill_package_id))
        except ValueError as exc:
            raise BadRequestError("skill_package_id 无效") from exc
        row = await db.get(SkillPackage, sid)
    if row is None and skill_slug:
        from sqlalchemy import select

        row = await db.scalar(
            select(SkillPackage)
            .where(
                SkillPackage.tenant_id == ctx.tenant_id,
                SkillPackage.slug == skill_slug,
            )
            .limit(1)
        )
    if not row or is_marked_deleted(row) or not row.is_active:
        raise NotFoundError("技能包不存在或已停用")
    assert_tenant_access(ctx, row.tenant_id)
    return row


async def skill_read_reference(
    db: AsyncSession,
    ctx: TenantContext,
    params: dict,
    *,
    bound_skill_id: UUID | str | None = None,
) -> dict:
    """读取技能包内文本资源；``max_chars`` 夹取到 256..32000，越界路径抛异常。"""
    skill = await resolve_bound_skill(
        db,
        ctx,
        skill_package_id=params.get("skill_package_id") or bound_skill_id,
        skill_slug=params.get("skill_slug"),
    )
    path = str(params.get("path") or "").strip()
    if not path:
        raise BadRequestError("path 不能为空")
    max_chars = int(params.get("max_chars") or 12_000)
    max_chars = min(max(max_chars, 256), 32_000)
    try:
        return read_skill_resource(ctx.tenant_id, skill.slug, path, max_chars=max_chars)
    except FileNotFoundError as exc:
        raise NotFoundError("文件不存在") from exc
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc


async def skill_run_script(
    db: AsyncSession,
    ctx: TenantContext,
    params: dict,
    *,
    bound_skill_id: UUID | str | None = None,
    actor_user_id: UUID | None = None,
) -> dict:
    """在 Runner 沙箱执行技能脚本，并写入会话审计；需启用 ``MCP_RUNNER_ENABLED``。"""
    settings = get_settings()
    if not settings.mcp_runner_enabled:
        raise BadRequestError("脚本执行需要启用 MCP Runner（MCP_RUNNER_ENABLED=true）")

    skill = await resolve_bound_skill(
        db,
        ctx,
        skill_package_id=params.get("skill_package_id") or bound_skill_id,
        skill_slug=params.get("skill_slug"),
    )
    path = str(params.get("path") or "").strip()
    if not path:
        raise BadRequestError("path 不能为空")

    try:
        source = read_skill_script_source(ctx.tenant_id, skill.slug, path)
    except FileNotFoundError as exc:
        raise NotFoundError("脚本不存在") from exc
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc

    if path.endswith(".sh"):
        raise BadRequestError("暂不支持直接执行 .sh，请使用 Python 脚本")

    source = validate_script_source(source)
    script_params = (
        params.get("params")
        if isinstance(params.get("params"), dict)
        else {k: v for k, v in params.items() if k not in ("path", "skill_package_id", "skill_slug", "params")}
    )

    from miles_portal.tenant.mcp.runner.audit import write_script_runner_session
    from miles_portal.tenant.mcp.runner.client import RunnerClient

    timeout_sec = min(max(int(params.get("timeout_sec") or 30), 1), 120)
    memory_mb = min(max(int(params.get("max_memory_mb") or 512), 128), 2048)
    started = time.monotonic()
    try:
        output = await RunnerClient().exec_script(
            tenant_id=ctx.tenant_id,
            source=source,
            params=script_params,
            tool_id=None,
            actor_user_id=actor_user_id or ctx.user_id,
            max_runtime_sec=timeout_sec,
            max_memory_mb=memory_mb,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        await write_script_runner_session(
            db,
            tenant_id=ctx.tenant_id,
            tool_id=None,
            actor_user_id=actor_user_id or ctx.user_id,
            source=source,
            status="success",
            duration_ms=duration_ms,
            tool_name=f"skill:{skill.slug}:{path}",
        )
        return {"path": path, "output": output}
    except BadRequestError as e:
        duration_ms = int((time.monotonic() - started) * 1000)
        await write_script_runner_session(
            db,
            tenant_id=ctx.tenant_id,
            tool_id=None,
            actor_user_id=actor_user_id or ctx.user_id,
            source=source,
            status="error",
            duration_ms=duration_ms,
            error_message=e.message,
            tool_name=f"skill:{skill.slug}:{path}",
        )
        raise
