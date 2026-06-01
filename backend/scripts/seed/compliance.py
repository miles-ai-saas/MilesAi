"""租户敏感词库种子：多词库、词条、扫描绑定（幂等，可重复执行）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.soft_delete import not_deleted
from app.models.platform.tenant import Tenant
from app.tenant.compliance.models import (
    COMPLIANCE_SCOPE_TENANT,
    DEFAULT_WORD_LIBRARY_NAME,
    ComplianceLibraryBinding,
    LibraryWordBinding,
    SensitiveAction,
    SensitiveWordEntry,
    WordLibrary,
)

# 词库定义：bind_scan=True 的库会加入租户「参与扫描」绑定
SEED_LIBRARIES: list[dict] = [
    {
        "name": DEFAULT_WORD_LIBRARY_NAME,
        "description": "系统默认词库，迁移与种子共用；覆盖通用安全与涉密类词条。",
        "sort_order": 0,
        "bind_scan": True,
        "words": [
            ("违禁品", SensitiveAction.BLOCK),
            ("涉密", SensitiveAction.BLOCK),
            ("国家秘密", SensitiveAction.BLOCK),
            ("内部资料外传", SensitiveAction.WARN),
            ("未授权披露", SensitiveAction.WARN),
        ],
    },
    {
        "name": "广告法合规",
        "description": "广告与营销文案常见违规表述（示例）。",
        "sort_order": 10,
        "bind_scan": True,
        "words": [
            ("虚假宣传", SensitiveAction.BLOCK),
            ("绝对化用语", SensitiveAction.WARN),
            ("国家级", SensitiveAction.WARN),
            ("最好", SensitiveAction.WARN),
            ("第一", SensitiveAction.WARN),
            ("包治百病", SensitiveAction.BLOCK),
        ],
    },
    {
        "name": "客服外呼",
        "description": "客服/外呼场景敏感表述（示例）。",
        "sort_order": 20,
        "bind_scan": True,
        "words": [
            ("辱骂", SensitiveAction.BLOCK),
            ("威胁用户", SensitiveAction.BLOCK),
            ("私下交易", SensitiveAction.WARN),
            ("加微信转账", SensitiveAction.WARN),
        ],
    },
    {
        "name": "观察名单（未默认启用扫描）",
        "description": "预置观察词条库；默认不勾选参与扫描，可在合规页手动启用。",
        "sort_order": 90,
        "bind_scan": False,
        "words": [
            ("竞品诋毁", SensitiveAction.WARN),
            ("内部未公开", SensitiveAction.WARN),
        ],
    },
]

# 跨库共享词面（一词多库，处置方式可按库不同）
SEED_MULTI_LIBRARY_WORDS: list[tuple[str, dict[str, SensitiveAction]]] = [
    (
        "虚假宣传",
        {
            DEFAULT_WORD_LIBRARY_NAME: SensitiveAction.WARN,
            "广告法合规": SensitiveAction.BLOCK,
        },
    ),
]


async def _ensure_scan_binding(session: AsyncSession, tenant_id, library_id) -> None:
    exists = await session.scalar(
        select(ComplianceLibraryBinding.id).where(
            ComplianceLibraryBinding.tenant_id == tenant_id,
            ComplianceLibraryBinding.library_id == library_id,
            ComplianceLibraryBinding.scope == COMPLIANCE_SCOPE_TENANT,
            not_deleted(ComplianceLibraryBinding),
        )
    )
    if not exists:
        session.add(
            ComplianceLibraryBinding(
                tenant_id=tenant_id,
                library_id=library_id,
                scope=COMPLIANCE_SCOPE_TENANT,
            )
        )


async def _get_or_create_entry(session: AsyncSession, tenant_id, word: str) -> SensitiveWordEntry:
    entry = await session.scalar(
        select(SensitiveWordEntry).where(
            SensitiveWordEntry.tenant_id == tenant_id,
            SensitiveWordEntry.word == word,
            not_deleted(SensitiveWordEntry),
        )
    )
    if entry:
        return entry
    entry = SensitiveWordEntry(tenant_id=tenant_id, word=word)
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def _ensure_binding(
    session: AsyncSession,
    *,
    library_id,
    entry_id,
    action: SensitiveAction,
) -> None:
    exists = await session.scalar(
        select(LibraryWordBinding.id).where(
            LibraryWordBinding.library_id == library_id,
            LibraryWordBinding.entry_id == entry_id,
            not_deleted(LibraryWordBinding),
        )
    )
    if exists:
        return
    session.add(
        LibraryWordBinding(
            library_id=library_id,
            entry_id=entry_id,
            action=action,
            is_active=True,
        )
    )


async def _get_or_create_library(
    session: AsyncSession,
    tenant_id,
    *,
    name: str,
    description: str | None,
    sort_order: int,
) -> WordLibrary:
    lib = await session.scalar(
        select(WordLibrary).where(
            WordLibrary.tenant_id == tenant_id,
            WordLibrary.name == name,
            not_deleted(WordLibrary),
        )
    )
    if lib:
        return lib
    lib = WordLibrary(
        tenant_id=tenant_id,
        name=name,
        description=description,
        is_active=True,
        sort_order=sort_order,
    )
    session.add(lib)
    await session.flush()
    await session.refresh(lib)
    return lib


async def seed_compliance_for_tenant(session: AsyncSession, tenant_id) -> None:
    library_by_name: dict[str, WordLibrary] = {}

    for spec in SEED_LIBRARIES:
        lib = await _get_or_create_library(
            session,
            tenant_id,
            name=spec["name"],
            description=spec.get("description"),
            sort_order=int(spec.get("sort_order", 0)),
        )
        library_by_name[spec["name"]] = lib
        if spec.get("bind_scan"):
            await _ensure_scan_binding(session, tenant_id, lib.id)

        for word, action in spec.get("words", []):
            entry = await _get_or_create_entry(session, tenant_id, word)
            await _ensure_binding(session, library_id=lib.id, entry_id=entry.id, action=action)

    for word, lib_actions in SEED_MULTI_LIBRARY_WORDS:
        entry = await _get_or_create_entry(session, tenant_id, word)
        for lib_name, action in lib_actions.items():
            lib = library_by_name.get(lib_name)
            if not lib:
                lib = await session.scalar(
                    select(WordLibrary).where(
                        WordLibrary.tenant_id == tenant_id,
                        WordLibrary.name == lib_name,
                        not_deleted(WordLibrary),
                    )
                )
            if lib:
                await _ensure_binding(session, library_id=lib.id, entry_id=entry.id, action=action)

    await session.flush()


async def seed_compliance(session: AsyncSession) -> None:
    tenant_ids = (await session.execute(select(Tenant.id))).scalars().all()
    for tid in tenant_ids:
        await seed_compliance_for_tenant(session, tid)
