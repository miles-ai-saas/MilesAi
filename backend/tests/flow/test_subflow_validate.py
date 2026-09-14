"""SubFlow 校验仓储契约注入测试（fake repo，不触 DB）。"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from miles_ai.flow_runtime.subflow.validate import validate_subflow_references
from miles_core.models.flow import FlowStatus


def _graph(sub_flow_id: str | None = None, **data_extra: object) -> dict:
    data: dict = {"type": "SubFlow"}
    if sub_flow_id is not None:
        data["sub_flow_id"] = sub_flow_id
    data.update(data_extra)
    return {
        "nodes": [{"id": "sf1", "type": "SubFlow", "data": data}],
        "edges": [],
    }


def _flow(tenant_id: UUID, *, status: FlowStatus = FlowStatus.PUBLISHED, current_version: int = 1):
    # 不设 deleted_at，使 is_marked_deleted 判为未删
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id,
        status=status,
        current_version=current_version,
    )


class FakeRepo:
    def __init__(self, *, flow=None, version=None) -> None:
        self._flow = flow
        self._version = version
        self.get_by_id_calls: list[UUID] = []
        self.get_version_calls: list[tuple[UUID, int]] = []

    async def get_by_id(self, entity_id: UUID, *, include_deleted: bool = False):
        self.get_by_id_calls.append(entity_id)
        return self._flow

    async def get_version(self, flow_id: UUID, version: int):
        self.get_version_calls.append((flow_id, version))
        return self._version


class RaisingRepo:
    """任何方法被调用即失败，证明 A 组用例不触碰仓储。"""

    async def get_by_id(self, *args, **kwargs):
        raise AssertionError("get_by_id 不应被调用")

    async def get_version(self, *args, **kwargs):
        raise AssertionError("get_version 不应被调用")


# ---- A：无需 repo 的校验 ----


@pytest.mark.asyncio
async def test_missing_sub_flow_id_no_repo_call():
    errors = await validate_subflow_references(
        RaisingRepo(),
        _graph(),
        tenant_id=uuid4(),
        current_flow_id=None,
    )
    assert [e["code"] for e in errors] == ["missing_sub_flow_id"]


@pytest.mark.asyncio
async def test_subflow_self_error():
    current_flow_id = uuid4()
    # self 分支在触碰仓储前即产出错误码；但 current_flow_id 存在时
    # 后续环/深度检查会探仓储，故这里用返回 None 的假 repo。
    errors = await validate_subflow_references(
        FakeRepo(flow=None),
        _graph(str(current_flow_id)),
        tenant_id=uuid4(),
        current_flow_id=current_flow_id,
    )
    assert "subflow_self" in [e["code"] for e in errors]


@pytest.mark.asyncio
async def test_invalid_sub_flow_id_no_repo_call():
    errors = await validate_subflow_references(
        RaisingRepo(),
        _graph("not-a-uuid"),
        tenant_id=uuid4(),
        current_flow_id=None,
    )
    assert [e["code"] for e in errors] == ["missing_sub_flow_id"]


# ---- B：子流程不存在 ----


@pytest.mark.asyncio
async def test_subflow_not_found():
    tenant_id = uuid4()
    repo = FakeRepo(flow=None)
    errors = await validate_subflow_references(
        repo,
        _graph(str(uuid4())),
        tenant_id=tenant_id,
        current_flow_id=None,
    )
    assert [e["code"] for e in errors] == ["subflow_not_found"]
    assert len(repo.get_by_id_calls) == 1


# ---- C：子流程未发布 ----


@pytest.mark.asyncio
async def test_subflow_not_published():
    tenant_id = uuid4()
    repo = FakeRepo(flow=_flow(tenant_id, status=FlowStatus.DRAFT, current_version=1))
    errors = await validate_subflow_references(
        repo,
        _graph(str(uuid4())),
        tenant_id=tenant_id,
        current_flow_id=None,
    )
    assert [e["code"] for e in errors] == ["subflow_not_published"]


# ---- D：pinned 版本缺失 ----


@pytest.mark.asyncio
async def test_subflow_pinned_missing():
    tenant_id = uuid4()
    repo = FakeRepo(flow=_flow(tenant_id), version=None)
    errors = await validate_subflow_references(
        repo,
        _graph(str(uuid4()), version_policy="pinned", pinned_version=9),
        tenant_id=tenant_id,
        current_flow_id=None,
    )
    assert [e["code"] for e in errors] == ["subflow_pinned_missing"]
    assert repo.get_version_calls
    assert repo.get_version_calls[0][1] == 9


# ---- E：通过 ----


@pytest.mark.asyncio
async def test_validate_subflow_references_passes():
    tenant_id = uuid4()
    repo = FakeRepo(
        flow=_flow(tenant_id, status=FlowStatus.PUBLISHED, current_version=1),
        version=SimpleNamespace(graph_json={"nodes": [], "edges": []}),
    )
    errors = await validate_subflow_references(
        repo,
        _graph(str(uuid4())),
        tenant_id=tenant_id,
        current_flow_id=None,
    )
    assert errors == []
    assert len(repo.get_by_id_calls) == 1


# ---- F：反查环、深度上限与错误顺序 ----


def _node(node_id: str, sub_flow_id: str | None, **extra: object) -> dict:
    data: dict = {"type": "SubFlow"}
    if sub_flow_id is not None:
        data["sub_flow_id"] = sub_flow_id
    data.update(extra)
    return {"id": node_id, "type": "SubFlow", "data": data}


def _graph_of(*nodes: dict) -> dict:
    return {"nodes": list(nodes), "edges": []}


class GraphRepo:
    """按 flow_id 索引流程与其当前版本图，并记录调用轨迹。"""

    def __init__(self) -> None:
        self.flows: dict[UUID, object] = {}
        self.graphs: dict[UUID, dict] = {}
        self.by_id_calls: list[UUID] = []
        self.version_calls: list[tuple[UUID, int]] = []

    def add(
        self,
        tenant_id: UUID,
        graph: dict,
        *,
        status: FlowStatus = FlowStatus.PUBLISHED,
        current_version: int = 1,
        deleted_at: object = None,
    ):
        flow = SimpleNamespace(
            id=uuid4(),
            tenant_id=tenant_id,
            status=status,
            current_version=current_version,
            deleted_at=deleted_at,
        )
        self.flows[flow.id] = flow
        self.graphs[flow.id] = graph
        return flow

    async def get_by_id(self, entity_id: UUID, *, include_deleted: bool = False):  # noqa: ANN001, ARG002
        self.by_id_calls.append(entity_id)
        return self.flows.get(entity_id)

    async def get_version(self, flow_id: UUID, version: int):  # noqa: ANN001
        self.version_calls.append((flow_id, version))
        graph = self.graphs.get(flow_id)
        return SimpleNamespace(graph_json=graph) if graph is not None else None


@pytest.mark.asyncio
async def test_reverse_reference_produces_cycle_error():
    tenant = uuid4()
    repo = GraphRepo()
    root = repo.add(tenant, _graph_of())
    child = repo.add(tenant, _graph_of())
    repo.graphs[root.id] = _graph_of(_node("sf1", str(child.id)))
    repo.graphs[child.id] = _graph_of(_node("sf2", str(root.id)))

    errors = await validate_subflow_references(
        repo,
        repo.graphs[root.id],
        tenant_id=tenant,
        current_flow_id=root.id,
    )

    assert [e["code"] for e in errors] == ["subflow_cycle"]
    assert errors[0]["node_id"] == "sf1"
    assert errors[0]["message"] == f"子流程依赖存在环：{child.id} → {root.id}"


@pytest.mark.asyncio
async def test_chain_beyond_max_depth_is_reported_without_node_id():
    tenant = uuid4()
    repo = GraphRepo()
    # root → a → b → c → d：深度 4 超过 MAX_SUBFLOW_DEPTH（3）
    d = repo.add(tenant, _graph_of())
    c = repo.add(tenant, _graph_of(_node("n", str(d.id))))
    b = repo.add(tenant, _graph_of(_node("n", str(c.id))))
    a = repo.add(tenant, _graph_of(_node("n", str(b.id))))
    root = repo.add(tenant, _graph_of(_node("sf1", str(a.id))))

    errors = await validate_subflow_references(
        repo,
        repo.graphs[root.id],
        tenant_id=tenant,
        current_flow_id=root.id,
    )

    assert [e["code"] for e in errors] == ["subflow_max_depth"]
    assert errors[0]["node_id"] is None
    assert "3" in errors[0]["message"]


@pytest.mark.asyncio
async def test_error_order_is_node_then_cycle_then_depth():
    """三类错误按 节点级 → 环 → 深度 的固定顺序累积。"""
    tenant = uuid4()
    repo = GraphRepo()
    d = repo.add(tenant, _graph_of())
    c = repo.add(tenant, _graph_of(_node("n", str(d.id))))
    b = repo.add(tenant, _graph_of(_node("n", str(c.id))))
    a = repo.add(tenant, _graph_of(_node("n", str(b.id))))
    child = repo.add(tenant, _graph_of())
    root = repo.add(tenant, _graph_of())
    repo.graphs[child.id] = _graph_of(_node("sf_back", str(root.id)))
    repo.graphs[root.id] = _graph_of(
        _node("bad", None),
        _node("sf_cycle", str(child.id)),
        _node("sf_deep", str(a.id)),
    )

    errors = await validate_subflow_references(
        repo,
        repo.graphs[root.id],
        tenant_id=tenant,
        current_flow_id=root.id,
    )

    assert [e["code"] for e in errors] == [
        "missing_sub_flow_id",
        "subflow_cycle",
        "subflow_max_depth",
    ]


@pytest.mark.asyncio
async def test_current_flow_id_absent_skips_cycle_and_depth_checks():
    tenant = uuid4()
    repo = GraphRepo()
    child = repo.add(tenant, _graph_of())
    graph = _graph_of(_node("sf1", str(child.id)))

    errors = await validate_subflow_references(repo, graph, tenant_id=tenant, current_flow_id=None)

    assert errors == []
    # 只查了子流程本身；未做反向引用遍历（否则会再查一次）
    assert repo.by_id_calls == [child.id]


@pytest.mark.asyncio
async def test_invalid_sub_flow_id_does_not_crash_cycle_scan():
    """格式非法的 sub_flow_id 已由节点级校验记为错误，反查环阶段不得因 UUID() 抛错。

    回归：此前 ``current_flow_id`` 非空时，第二阶段会对同一节点再调 ``UUID(sub_raw)``
    并抛 ``ValueError``，导致保存流程报 500 而非返回结构化错误。
    """
    tenant = uuid4()
    repo = GraphRepo()
    graph = _graph_of(
        _node("bad", "not-a-uuid"),
        _node("ok", str(repo.add(tenant, _graph_of()).id)),
    )

    errors = await validate_subflow_references(repo, graph, tenant_id=tenant, current_flow_id=uuid4())

    assert [e["code"] for e in errors] == ["missing_sub_flow_id"]
    assert errors[0]["node_id"] == "bad"


# ---- G：子流程归属与版本策略细节 ----


@pytest.mark.asyncio
async def test_child_of_other_tenant_is_not_found():
    tenant, other = uuid4(), uuid4()
    repo = GraphRepo()
    child = repo.add(other, _graph_of())

    errors = await validate_subflow_references(
        repo,
        _graph_of(_node("sf1", str(child.id))),
        tenant_id=tenant,
        current_flow_id=None,
    )

    assert [e["code"] for e in errors] == ["subflow_not_found"]


@pytest.mark.asyncio
async def test_soft_deleted_child_is_not_found():
    tenant = uuid4()
    repo = GraphRepo()
    child = repo.add(tenant, _graph_of(), deleted_at=datetime.now(UTC))

    errors = await validate_subflow_references(
        repo,
        _graph_of(_node("sf1", str(child.id))),
        tenant_id=tenant,
        current_flow_id=None,
    )

    assert [e["code"] for e in errors] == ["subflow_not_found"]


@pytest.mark.asyncio
async def test_published_child_without_version_is_reported():
    tenant = uuid4()
    repo = GraphRepo()
    child = repo.add(tenant, _graph_of(), current_version=0)

    errors = await validate_subflow_references(
        repo,
        _graph_of(_node("sf1", str(child.id))),
        tenant_id=tenant,
        current_flow_id=None,
    )

    assert [e["code"] for e in errors] == ["subflow_not_published"]
    assert "无可用版本" in errors[0]["message"]


@pytest.mark.asyncio
async def test_pinned_policy_without_pinned_version_reports_without_lookup():
    tenant = uuid4()
    repo = GraphRepo()
    child = repo.add(tenant, _graph_of())

    errors = await validate_subflow_references(
        repo,
        _graph_of(_node("sf1", str(child.id), version_policy="pinned")),
        tenant_id=tenant,
        current_flow_id=None,
    )

    assert [e["code"] for e in errors] == ["subflow_pinned_missing"]
    assert repo.version_calls == []  # 缺 pinned_version 时不查版本


@pytest.mark.asyncio
async def test_pinned_policy_with_existing_version_passes():
    tenant = uuid4()
    repo = GraphRepo()
    child = repo.add(tenant, _graph_of())

    errors = await validate_subflow_references(
        repo,
        _graph_of(_node("sf1", str(child.id), version_policy="pinned", pinned_version=2)),
        tenant_id=tenant,
        current_flow_id=None,
    )

    assert errors == []
    assert repo.version_calls == [(child.id, 2)]


@pytest.mark.asyncio
async def test_version_policy_is_trimmed_and_lowercased():
    tenant = uuid4()
    repo = GraphRepo()
    child = repo.add(tenant, _graph_of())

    errors = await validate_subflow_references(
        repo,
        _graph_of(_node("sf1", str(child.id), version_policy=" PINNED ")),
        tenant_id=tenant,
        current_flow_id=None,
    )

    # 归一化后命中 pinned 分支（缺 pinned_version），而非回退到 published 校验
    assert [e["code"] for e in errors] == ["subflow_pinned_missing"]
