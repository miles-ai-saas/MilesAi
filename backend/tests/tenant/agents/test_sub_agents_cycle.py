"""子智能体绑定的环检测（``_would_create_cycle``）。

绑定表 ``agt_sub_agent_bindings`` 没有 ``tenant_id`` 列，原实现无条件 ``SELECT``
全部边——既随租户/绑定总量线性变慢，又把其他租户的协作关系读进内存。本文件锁定
两件事：环判定本身正确；查询被收窄到本租户。
"""

from uuid import uuid4

import pytest

from miles_portal.tenant.agents.services.sub_agents import _would_create_cycle


class _Result:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def all(self) -> list[tuple]:
        return self._rows


class _CapturingDb:
    """记录执行的语句，并返回预置的边集。"""

    def __init__(self, edges: list[tuple]) -> None:
        self.edges = edges
        self.statements: list = []

    async def execute(self, stmt):  # noqa: ANN001
        self.statements.append(stmt)
        return _Result(self.edges)


async def test_empty_children_short_circuits_without_querying():
    db = _CapturingDb([])
    assert await _would_create_cycle(db, uuid4(), [], tenant_id=uuid4()) is False
    assert db.statements == []


async def test_detects_cycle_through_existing_edges():
    """已有 a→b，再加 b→a 即闭环。"""
    a, b = uuid4(), uuid4()
    db = _CapturingDb([(a, b)])
    assert await _would_create_cycle(db, b, [a], tenant_id=uuid4()) is True


async def test_disjoint_edges_do_not_form_cycle():
    a, b, c = uuid4(), uuid4(), uuid4()
    db = _CapturingDb([(a, b)])
    assert await _would_create_cycle(db, c, [a], tenant_id=uuid4()) is False


async def test_multi_hop_cycle_is_detected():
    """a→b→c 再加 c→a：多跳也要能检出。"""
    a, b, c = uuid4(), uuid4(), uuid4()
    db = _CapturingDb([(a, b), (b, c)])
    assert await _would_create_cycle(db, c, [a], tenant_id=uuid4()) is True


@pytest.mark.asyncio
async def test_cycle_query_is_scoped_to_the_tenant():
    """回归：必须按「父节点属于本租户」收窄，否则会全表加载所有租户的绑定边。"""
    db = _CapturingDb([])
    await _would_create_cycle(db, uuid4(), [uuid4()], tenant_id=uuid4())

    assert len(db.statements) == 1
    sql = str(db.statements[0].compile())
    assert "agt_agents.tenant_id" in sql
    assert "IN" in sql.upper()
