"""租户 HTTP 钩子种子（幂等，可重复执行）。

写入 HookDefinition + HookBinding；示例 Webhook 默认 **停用**，避免开发环境误打外网。
命令：``milesai seed hooks``
依赖：``seed tenant``。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.soft_delete import not_deleted
from miles_portal.tenant.hooks.models import (
    HookBinding,
    HookDefinition,
    HookScope,
    HookTrigger,
    HookType,
)
from miles_server.scripts.seed._helpers import list_tenant_ids

# 每条 spec：一条钩子定义 + 至少一条 binding（可与 create_hook API 行为一致）
SEED_HOOKS: list[dict] = [
    {
        "name": "调用后审计 Webhook（示例）",
        "hook_type": HookType.HTTP,
        "is_active": False,
        "config": {
            "url": "https://httpbin.org/post",
            "method": "POST",
            "on_failure": "ignore",
            "timeout": 5,
        },
        "bindings": [
            {
                "trigger": HookTrigger.AFTER_CALL,
                "scope": HookScope.GLOBAL,
                "target_id": None,
                "priority": 100,
            },
        ],
    },
    {
        "name": "调用前鉴权检查（示例）",
        "hook_type": HookType.HTTP,
        "is_active": False,
        "config": {
            "url": "https://httpbin.org/post",
            "method": "POST",
            "on_failure": "fail_request",
            "timeout": 3,
        },
        "bindings": [
            {
                "trigger": HookTrigger.BEFORE_CALL,
                "scope": HookScope.GLOBAL,
                "target_id": None,
                "priority": 50,
            },
        ],
    },
    {
        "name": "推理后采样上报（示例）",
        "hook_type": HookType.HTTP,
        "is_active": False,
        "config": {
            "url": "https://httpbin.org/post",
            "method": "POST",
            "on_failure": "ignore",
            "timeout": 5,
        },
        "bindings": [
            {
                "trigger": HookTrigger.AFTER_REASONING,
                "scope": HookScope.GLOBAL,
                "target_id": None,
                "priority": 100,
            },
        ],
    },
    {
        "name": "工具调用审计（示例）",
        "hook_type": HookType.HTTP,
        "is_active": False,
        "config": {
            "url": "https://httpbin.org/post",
            "method": "POST",
            "on_failure": "ignore",
            "timeout": 5,
        },
        "bindings": [
            {
                "trigger": HookTrigger.AFTER_TOOL,
                "scope": HookScope.GLOBAL,
                "target_id": None,
                "priority": 100,
            },
        ],
    },
    {
        "name": "出错告警 Webhook（示例）",
        "hook_type": HookType.HTTP,
        "is_active": False,
        "config": {
            "url": "https://httpbin.org/post",
            "method": "POST",
            "on_failure": "ignore",
            "timeout": 10,
        },
        "bindings": [
            {
                "trigger": HookTrigger.ON_ERROR,
                "scope": HookScope.GLOBAL,
                "target_id": None,
                "priority": 100,
            },
        ],
    },
    {
        "name": "双时机审计（示例）",
        "hook_type": HookType.HTTP,
        "is_active": False,
        "config": {
            "url": "https://httpbin.org/post",
            "method": "POST",
            "on_failure": "ignore",
            "timeout": 5,
        },
        "bindings": [
            {
                "trigger": HookTrigger.BEFORE_CALL,
                "scope": HookScope.GLOBAL,
                "target_id": None,
                "priority": 200,
            },
            {
                "trigger": HookTrigger.ON_ERROR,
                "scope": HookScope.GLOBAL,
                "target_id": None,
                "priority": 200,
            },
        ],
    },
]


async def _get_or_create_hook(
    session: AsyncSession,
    tenant_id,
    spec: dict,
) -> HookDefinition:
    row = await session.scalar(
        select(HookDefinition).where(
            HookDefinition.tenant_id == tenant_id,
            HookDefinition.name == spec["name"],
            not_deleted(HookDefinition),
        )
    )
    if row:
        return row

    row = HookDefinition(
        tenant_id=tenant_id,
        name=spec["name"],
        hook_type=spec["hook_type"],
        config=dict(spec.get("config") or {}),
        is_active=bool(spec.get("is_active", False)),
    )
    session.add(row)
    await session.flush()

    for b in spec.get("bindings") or []:
        binding = HookBinding(
            tenant_id=tenant_id,
            hook_id=row.id,
            scope=b["scope"],
            target_id=b.get("target_id"),
            trigger=b["trigger"],
            priority=int(b.get("priority", 100)),
            is_active=True,
        )
        session.add(binding)
    await session.flush()
    await session.refresh(row)
    return row


async def seed_hooks_for_tenant(session: AsyncSession, tenant_id) -> int:
    created = 0
    for spec in SEED_HOOKS:
        before = await session.scalar(
            select(HookDefinition.id).where(
                HookDefinition.tenant_id == tenant_id,
                HookDefinition.name == spec["name"],
                not_deleted(HookDefinition),
            )
        )
        await _get_or_create_hook(session, tenant_id, spec)
        if before is None:
            created += 1
    await session.flush()
    return created


async def seed_hooks(session: AsyncSession) -> None:
    total_created = 0
    for tenant_id in await list_tenant_ids(session):
        total_created += await seed_hooks_for_tenant(session, tenant_id)
    print(f">>> hooks seed: created {total_created} hook definition(s) (sample webhooks default inactive; enable after replacing URL)")
