"""连接池参数接线：``Settings`` 的池配置必须真的传到 engine 上。

对话/生成链路的事务会跨越 LLM 调用（可达数十秒），并发上限因此直接受池容量约束。
若参数只是声明在 ``Settings`` 里而没接上 engine，生产环境调大也不会生效，
排查连接超时问题时极易误判。

注意池参数的默认值恰好等于 SQLAlchemy 原默认，所以只断言默认值无法区分
「接线正确」与「压根没传参」（两者行为完全一致）。这里用非默认值 + 直接调
``build_engine`` 来真正验证接线。
"""

import pytest

from miles_core.config import Settings, get_settings
from miles_core.infra.db.async_session import build_engine, dispose_loop_engines, get_engine


# 下面三个用例的局限：断言值恰等于 SQLAlchemy 原默认（5 / 10 / 30s），故「接线正确」与
# 「压根没传参」行为完全一致，无法区分。真正能证伪接线的是
# tests/infra/test_loop_aware_engine.py::test_engine_receives_configured_pool_params
# 与本文件下方 test_build_engine_wires_non_default_pool_params（走非默认值）。
# 另外它们各自会构建真 engine：注册表的 value 强引用 engine，必须显式 dispose，
# 否则条目连同 loop 一起被钉住（弱键救不了，见 async_session.py 模块 docstring）。
@pytest.mark.asyncio
async def test_pool_size_follows_settings():
    try:
        assert get_engine().pool.size() == get_settings().db_pool_size
    finally:
        await dispose_loop_engines()


@pytest.mark.asyncio
async def test_max_overflow_follows_settings():
    try:
        assert get_engine().pool._max_overflow == get_settings().db_max_overflow
    finally:
        await dispose_loop_engines()


@pytest.mark.asyncio
async def test_pool_timeout_follows_settings():
    try:
        assert get_engine().pool._timeout == get_settings().db_pool_timeout
    finally:
        await dispose_loop_engines()


def test_defaults_keep_sqlalchemy_original_values():
    """显式化不该顺手改行为：默认仍是 SQLAlchemy 原默认 5 / 10 / 30s。"""
    settings = get_settings()
    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 10
    assert settings.db_pool_timeout == 30.0


@pytest.mark.asyncio
async def test_build_engine_wires_non_default_pool_params(monkeypatch):
    """用非默认值验证真的接了线——默认值断言对漏传参数是「假绿」。"""
    monkeypatch.setenv("DB_POOL_SIZE", "9")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "13")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "7.5")

    eng = build_engine(Settings())
    try:
        assert eng.pool.size() == 9
        assert eng.pool._max_overflow == 13
        assert eng.pool._timeout == 7.5
    finally:
        await eng.dispose()
