"""画布 ComplianceCheck 节点敏感词表加载器（L1 装配）。

``build_scan_words_loader`` 构造 ``RunContext.load_scan_words`` 回调：按 tenant_id
短会话加载租户已绑定启用词库的启用词条（``load_tenant_scan_words``），供
flow_runtime ComplianceCheck 节点使用；装配点为 chat_rag.flow_run_context 与
flows flow debug-run。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from miles_core.infra.db import short_db_session
from miles_portal.tenant.compliance.services.word_resolve import load_tenant_scan_words


def build_scan_words_loader() -> Callable[[str], Awaitable[Any]]:
    """构造 RunContext.load_scan_words 回调（内部短会话加载词表）。"""

    async def _loader(tenant_id: str) -> Any:
        tid = UUID(str(tenant_id))
        async with short_db_session() as db:
            return await load_tenant_scan_words(db, tid)

    return _loader
