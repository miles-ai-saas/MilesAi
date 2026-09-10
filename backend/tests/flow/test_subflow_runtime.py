"""运行期子图加载测试：resolve_subflow_graph 契约仓储 + SubFlow/LoopNode 回调装配。"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError
from app.flow_runtime.nodes.loop_nodes import loop_node
from app.flow_runtime.nodes.subflow_nodes import sub_flow
from app.flow_runtime.subflow.resolve import resolve_subflow_graph
from app.flow_runtime.types import RunContext
from app.models.flow import FlowStatus


def _flow(
    tenant_id,
    *,
    flow_id=None,
    status: FlowStatus = FlowStatus.PUBLISHED,
    current_version: int = 1,
):
    # 不设 deleted_at，使 is_marked_deleted 判为未删
    return SimpleNamespace(
        id=flow_id or uuid4(),
        tenant_id=tenant_id,
        status=status,
        current_version=current_version,
    )


class FakeRepo:
    def __init__(self, *, flow=None, version=None) -> None:
        self._flow = flow
        self._version = version
        self.get_by_id_calls: list = []
        self.get_version_calls: list = []

    async def get_by_id(self, entity_id, *, include_deleted: bool = False):
        self.get_by_id_calls.append(entity_id)
        return self._flow

    async def get_version(self, flow_id, version):
        self.get_version_calls.append((flow_id, version))
        return self._version


# ---- resolve_subflow_graph（契约仓储，不触 DB）----


@pytest.mark.asyncio
async def test_resolve_subflow_graph_published_returns_graph():
    tenant_id = uuid4()
    sub_id = uuid4()
    repo = FakeRepo(flow=_flow(tenant_id, flow_id=sub_id), version=SimpleNamespace(graph_json=None))

    graph = await resolve_subflow_graph(repo, {"sub_flow_id": str(sub_id)}, tenant_id)

    assert graph == {"nodes": [], "edges": []}
    assert repo.get_version_calls == [(sub_id, 1)]


@pytest.mark.asyncio
async def test_resolve_subflow_graph_pinned_missing_raises():
    tenant_id = uuid4()
    repo = FakeRepo(flow=_flow(tenant_id), version=None)

    with pytest.raises(BadRequestError, match="pinned 版本"):
        await resolve_subflow_graph(
            repo,
            {
                "sub_flow_id": str(uuid4()),
                "version_policy": "pinned",
                "pinned_version": 9,
            },
            tenant_id,
        )


@pytest.mark.asyncio
async def test_resolve_subflow_graph_not_published_raises():
    tenant_id = uuid4()
    repo = FakeRepo(
        flow=_flow(tenant_id, status=FlowStatus.DRAFT),
        version=SimpleNamespace(graph_json={"nodes": [], "edges": []}),
    )

    with pytest.raises(BadRequestError, match="未发布"):
        await resolve_subflow_graph(repo, {"sub_flow_id": str(uuid4())}, tenant_id)


# ---- SubFlow 节点 ----


@pytest.mark.asyncio
async def test_sub_flow_uses_injected_loader_and_run_subflow():
    sub_flow_id = str(uuid4())
    loaded: list = []

    async def fake_loader(node_data, tenant_id):
        loaded.append((node_data, tenant_id))
        return {"nodes": [], "edges": []}

    async def fake_run_subflow(graph_json, child_ctx):
        return SimpleNamespace(output="x", steps=[])

    ctx = RunContext(
        tenant_id=str(uuid4()),
        current_flow_id=str(uuid4()),
        load_subflow_graph=fake_loader,
        run_subflow=fake_run_subflow,
    )

    out = await sub_flow({"sub_flow_id": sub_flow_id}, {}, ctx)

    assert out["output"] == "x"
    assert out["child_flow_id"] == sub_flow_id
    assert loaded and loaded[0][1] == ctx.tenant_id


@pytest.mark.asyncio
async def test_sub_flow_missing_loader_raises():
    ctx = RunContext(tenant_id=str(uuid4()), current_flow_id=str(uuid4()))

    with pytest.raises(BadRequestError, match="子流程图加载回调"):
        await sub_flow({"sub_flow_id": str(uuid4())}, {}, ctx)


# ---- LoopNode 节点 ----


@pytest.mark.asyncio
async def test_loop_node_missing_loader_raises():
    ctx = RunContext(tenant_id=str(uuid4()), current_flow_id=str(uuid4()))

    with pytest.raises(BadRequestError, match="子流程图加载回调"):
        await loop_node({"sub_flow_id": str(uuid4())}, {}, ctx)


@pytest.mark.asyncio
async def test_loop_node_single_iteration_with_loader():
    async def fake_loader(node_data, tenant_id):
        return {"nodes": [], "edges": []}

    async def fake_run_subflow(graph_json, child_ctx):
        return SimpleNamespace(output={"done": True}, steps=[])

    ctx = RunContext(
        tenant_id=str(uuid4()),
        current_flow_id=str(uuid4()),
        load_subflow_graph=fake_loader,
        run_subflow=fake_run_subflow,
    )

    out = await loop_node({"sub_flow_id": str(uuid4()), "max_iterations": 1}, {}, ctx)

    assert out["iterations"] == 1
    assert out["output"] == {"done": True}
