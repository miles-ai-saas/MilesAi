"""sync 引擎延迟初始化：import db 包不立刻 create_engine。"""

from __future__ import annotations


def test_db_package_import_does_not_bind_sync_engine(monkeypatch):
    import miles_core.infra.db as db_pkg
    import miles_core.infra.db.sync as sync_mod

    sync_mod._sync_engine = None
    sync_mod._SyncSessionLocal = None

    # 重新导出路径：访问 get_db 不应触发 sync 引擎
    assert db_pkg.get_db is not None
    assert sync_mod._sync_engine is None

    created: list = []

    def fake_build(settings):  # noqa: ANN001
        eng = object()
        created.append(eng)
        return eng

    monkeypatch.setattr(sync_mod, "build_sync_engine", fake_build)
    eng = db_pkg.sync_engine
    assert eng is created[0]
    assert db_pkg.sync_engine is eng
