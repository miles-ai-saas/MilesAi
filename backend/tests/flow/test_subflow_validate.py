"""SubFlow 校验仓储契约注入测试（fake repo，不触 DB）。"""

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
