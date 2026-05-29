from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.deletion.cascade import before_delete_agent, before_delete_flow, before_delete_kb


@pytest.mark.asyncio
async def test_before_delete_agent_cleans_bindings_and_refs() -> None:
    agent_id = uuid4()
    db = AsyncMock()

    with (
        patch("app.deletion.cascade.unlink_agent_kb_bindings", new_callable=AsyncMock) as m1,
        patch("app.deletion.cascade.nullify_app_install_refs", new_callable=AsyncMock) as m2,
        patch("app.deletion.cascade.delete_hook_bindings_for_target", new_callable=AsyncMock) as m3,
    ):
        await before_delete_agent(db, agent_id)

    m1.assert_awaited_once_with(db, agent_id=agent_id)
    m2.assert_awaited_once_with(db, agent_id=agent_id)
    m3.assert_awaited_once()


@pytest.mark.asyncio
async def test_before_delete_kb_unlinks_bindings() -> None:
    kb_id = uuid4()
    db = AsyncMock()

    with (
        patch("app.deletion.cascade.unlink_agent_kb_bindings", new_callable=AsyncMock) as m1,
        patch("app.deletion.cascade.nullify_app_install_refs", new_callable=AsyncMock) as m2,
    ):
        await before_delete_kb(db, kb_id)

    m1.assert_awaited_once_with(db, kb_id=kb_id)
    m2.assert_awaited_once_with(db, kb_id=kb_id)


@pytest.mark.asyncio
async def test_before_delete_flow_cleans_versions_and_refs() -> None:
    flow_id = uuid4()
    db = AsyncMock()

    with (
        patch("app.deletion.cascade.clear_agents_published_flow_ref", new_callable=AsyncMock) as m1,
        patch("app.deletion.cascade.nullify_app_install_refs", new_callable=AsyncMock) as m2,
        patch("app.deletion.cascade.delete_hook_bindings_for_target", new_callable=AsyncMock) as m3,
        patch("app.deletion.cascade.delete_flow_versions", new_callable=AsyncMock) as m4,
    ):
        await before_delete_flow(db, flow_id)

    m1.assert_awaited_once_with(db, flow_id)
    m2.assert_awaited_once_with(db, flow_id=flow_id)
    m3.assert_awaited_once()
    m4.assert_awaited_once_with(db, flow_id)
