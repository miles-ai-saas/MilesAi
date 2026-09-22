"""subflow_loader 适配层定向单测：短会话仓储构造与 tenant_id 解析。

monkeypatch 均打到 ``subflow_loader`` 模块命名空间（from-import 绑定）；
AsyncSessionLocal/FlowRepository/resolve_subflow_graph 用假实现替换，不触真实 DB。
"""

import asyncio
from uuid import UUID, uuid4

from miles_portal.tenant.flows.services import subflow_loader as loader_mod
from miles_portal.tenant.flows.services.subflow_loader import build_subflow_graph_loader


class _FakeSession:
    """假 async 上下文管理器：__aenter__ 返回传入的假 db。"""

    def __init__(self, db) -> None:
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_build_subflow_graph_loader_delegates(monkeypatch):
    fake_db = object()
    repo_db_calls: list = []

    class FakeRepo:
        def __init__(self, db) -> None:
            self.db = db
            repo_db_calls.append(db)

    resolve_calls: list = []

    async def fake_resolve(repo, node_data, tid):
        resolve_calls.append((repo, node_data, tid))
        return {"nodes": [], "edges": []}

    monkeypatch.setattr(loader_mod, "AsyncSessionLocal", lambda: _FakeSession(fake_db))
    monkeypatch.setattr(loader_mod, "FlowRepository", FakeRepo)
    monkeypatch.setattr(loader_mod, "resolve_subflow_graph", fake_resolve)

    loader = build_subflow_graph_loader()
    assert callable(loader)

    tenant_id = uuid4()
    node_data = {"sub_flow_id": str(uuid4())}

    graph = asyncio.run(loader(node_data, str(tenant_id)))

    assert graph == {"nodes": [], "edges": []}
    assert repo_db_calls == [fake_db]
    assert len(resolve_calls) == 1
    repo, passed_node_data, tid = resolve_calls[0]
    assert isinstance(repo, FakeRepo)
    assert repo.db is fake_db
    assert passed_node_data == node_data
    assert tid == tenant_id
    assert isinstance(tid, UUID)


def test_subflow_loader_builds_repository_on_its_own_session(monkeypatch):
    """子图加载站点：仓储建在自开的一次会话上，node_data/tenant_id 原样透传。"""
    fake_db = object()
    seen: list = []

    class FakeRepo:
        def __init__(self, db) -> None:
            self.db = db

    async def fake_resolve(repo, node_data, tid):
        seen.append((repo.db, node_data, tid))
        return {"nodes": [{"id": "n1"}], "edges": []}

    monkeypatch.setattr(loader_mod, "AsyncSessionLocal", lambda: _FakeSession(fake_db))
    monkeypatch.setattr(loader_mod, "FlowRepository", FakeRepo)
    monkeypatch.setattr(loader_mod, "resolve_subflow_graph", fake_resolve)

    tenant_id = uuid4()
    node_data = {"sub_flow_id": str(uuid4())}

    graph = asyncio.run(build_subflow_graph_loader()(node_data, str(tenant_id)))

    assert graph == {"nodes": [{"id": "n1"}], "edges": []}
    assert seen == [(fake_db, node_data, tenant_id)]
