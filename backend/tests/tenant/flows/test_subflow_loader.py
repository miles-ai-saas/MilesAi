"""subflow_loader 适配层定向单测：短会话仓储构造与 tenant_id 解析。

monkeypatch 均打到 ``subflow_loader`` 模块命名空间（from-import 绑定）；
short_db_session/FlowRepository/resolve_subflow_graph 用假实现替换，不触真实 DB。
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


class _Boom:
    """全局会话替身：被调用即失败，用来钉住「本模块不得再用全局会话」。"""

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("该站点必须走 short_db_session，不得回退全局 AsyncSessionLocal")


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

    monkeypatch.setattr(loader_mod, "short_db_session", lambda: _FakeSession(fake_db))
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


def test_subflow_loader_never_falls_back_to_global_session(monkeypatch):
    """子图加载站点：全局会话换成调用即炸替身，仓储仍必须建在短会话上。

    ``raising=False`` 是有意的：Task 1 之后本模块不再 import ``AsyncSessionLocal``，
    把一个「不存在的名字」换成替身，正是回退时能被抓到的原因。
    """
    fake_db = object()
    seen: list = []

    class FakeRepo:
        def __init__(self, db) -> None:
            self.db = db

    async def fake_resolve(repo, node_data, tid):
        seen.append((repo.db, node_data, tid))
        return {"nodes": [{"id": "n1"}], "edges": []}

    monkeypatch.setattr(loader_mod, "short_db_session", lambda: _FakeSession(fake_db), raising=False)
    monkeypatch.setattr(loader_mod, "AsyncSessionLocal", _Boom(), raising=False)
    monkeypatch.setattr(loader_mod, "FlowRepository", FakeRepo)
    monkeypatch.setattr(loader_mod, "resolve_subflow_graph", fake_resolve)

    tenant_id = uuid4()
    node_data = {"sub_flow_id": str(uuid4())}

    graph = asyncio.run(build_subflow_graph_loader()(node_data, str(tenant_id)))

    assert graph == {"nodes": [{"id": "n1"}], "edges": []}
    assert seen == [(fake_db, node_data, tenant_id)]
