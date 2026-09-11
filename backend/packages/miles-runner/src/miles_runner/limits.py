"""Runner 并发限制。"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from uuid import UUID


class RunnerLimits:
    """全局与租户级并发 semaphore。"""

    def __init__(self, *, max_global: int, max_per_tenant: int) -> None:
        self._global = asyncio.Semaphore(max_global)
        self._max_per_tenant = max_per_tenant
        self._tenant: dict[UUID, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(max_per_tenant))

    async def acquire(self, tenant_id: UUID) -> None:
        """先取全局信号量再取租户信号量；租户获取失败时回滚全局，避免额度泄漏。"""
        await self._global.acquire()
        tenant_sem = self._tenant[tenant_id]
        try:
            await tenant_sem.acquire()
        except Exception:
            self._global.release()
            raise

    def release(self, tenant_id: UUID) -> None:
        """释放租户与全局信号量（须与 ``acquire`` 成对调用）。"""
        self._tenant[tenant_id].release()
        self._global.release()
