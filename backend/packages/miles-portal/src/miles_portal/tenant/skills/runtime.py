"""技能包运行时：读取 reference、执行 scripts（供内置工具与 tool_agent 调用）。"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.config import get_settings
from miles_core.soft_delete import is_marked_deleted, not_deleted
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


async def bound_skill_slugs(
    db: AsyncSession,
    ctx: TenantContext,
    ids: Sequence[UUID | str],
) -> list[str]:
    """取绑定 ID 中仍可用的技能包 slug，供多绑定报错时点名可选值。"""
    parsed: list[UUID] = []
    for item in ids:
        try:
            parsed.append(UUID(str(item)))
        except (ValueError, TypeError):
            # 静默可接受：非法绑定项无法查库，跳过；合法项照常列出。
            continue
    if not parsed:
        return []
    from sqlalchemy import select

    rows = (
        await db.execute(
            select(SkillPackage.slug).where(
                SkillPackage.tenant_id == ctx.tenant_id,
                SkillPackage.id.in_(parsed),
                SkillPackage.is_active.is_(True),
                not_deleted(SkillPackage),
            )
        )
    ).scalars()
    return list(rows)


async def resolve_skill_for_tool(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    params: dict,
    bound_skill_ids: Sequence[UUID | str] | None = None,
) -> SkillPackage:
    """为 ``skill_*`` 工具选定技能包：显式入参 > 绑定集合。

    显式 ``params.skill_package_id`` 优先，其次 ``params.skill_slug``（多绑定下 LLM
    的消歧入口）；两者都缺时，绑定唯一则自动选用，绑定多个则报错并列出可选 slug ——
    静默挑第一个会让 LLM 读到「另一本技能手册」，属静默失败。
    """
    explicit_id = params.get("skill_package_id")
    if explicit_id:
        return await resolve_bound_skill(db, ctx, skill_package_id=explicit_id)
    explicit_slug = str(params.get("skill_slug") or "").strip()
    if explicit_slug:
        return await resolve_bound_skill(db, ctx, skill_slug=explicit_slug)

    ids = [i for i in (bound_skill_ids or []) if i]
    if not ids:
        raise BadRequestError("该工具需要智能体绑定技能包（config.skill_ids）")
    if len(ids) > 1:
        slugs = await bound_skill_slugs(db, ctx, ids)
        hint = "、".join(slugs) if slugs else "、".join(str(i) for i in ids)
        raise BadRequestError(f"智能体绑定了多个技能包（{hint}），请通过 skill_slug 指定要使用的技能包")
    return await resolve_bound_skill(db, ctx, skill_package_id=ids[0])


async def skill_read_reference(
    db: AsyncSession,
    ctx: TenantContext,
    params: dict,
    *,
    bound_skill_ids: Sequence[UUID | str] | None = None,
) -> dict:
    """读取技能包内文本资源；``max_chars`` 夹取到 256..32000，越界路径抛异常。"""
    skill = await resolve_skill_for_tool(db, ctx, params=params, bound_skill_ids=bound_skill_ids)
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
    bound_skill_ids: Sequence[UUID | str] | None = None,
    actor_user_id: UUID | None = None,
) -> dict:
    """在 Runner 沙箱执行技能脚本，并写入会话审计；需启用 ``MCP_RUNNER_ENABLED``。"""
    settings = get_settings()
    if not settings.mcp_runner_enabled:
        raise BadRequestError("脚本执行需要启用 MCP Runner（MCP_RUNNER_ENABLED=true）")

    skill = await resolve_skill_for_tool(db, ctx, params=params, bound_skill_ids=bound_skill_ids)
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

    from miles_portal.tenant.mcp.runner.audit import record_runner_session, write_script_runner_session
    from miles_portal.tenant.mcp.runner.client import RunnerClient

    timeout_sec = min(max(int(params.get("timeout_sec") or 30), 1), 120)
    memory_mb = min(max(int(params.get("max_memory_mb") or 512), 128), 2048)
    async with record_runner_session(
        write_script_runner_session,
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=actor_user_id or ctx.user_id,
        source=source,
        tool_name=f"skill:{skill.slug}:{path}",
    ):
        output = await RunnerClient().exec_script(
            tenant_id=ctx.tenant_id,
            source=source,
            params=script_params,
            tool_id=None,
            actor_user_id=actor_user_id or ctx.user_id,
            max_runtime_sec=timeout_sec,
            max_memory_mb=memory_mb,
        )
    return {"path": path, "output": output}
