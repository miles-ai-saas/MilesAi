"""调用记录升格评测用例。"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from miles_portal.tenant.eval.services.promote_from_call import promote_case_from_call, resolve_turn_texts


@pytest.mark.asyncio
async def test_resolve_turn_texts_falls_back_to_preview():
    call = SimpleNamespace(
        query_preview="问预览",
        answer_preview="答预览",
        conversation_id=None,
        trace_id=None,
        agent_id=uuid4(),
        tenant_id=uuid4(),
        created_at=datetime.now(UTC),
    )
    db = AsyncMock()
    q, a, used = await resolve_turn_texts(db, call=call, prefer_session_text=True)
    assert q == "问预览"
    assert a == "答预览"
    assert used is False


@pytest.mark.asyncio
async def test_promote_allows_failed_without_answer():
    ctx = SimpleNamespace(tenant_id=uuid4(), user_id=uuid4(), is_superuser=False)
    agent_id = uuid4()
    call_id = uuid4()
    call = MagicMock()
    call.id = call_id
    call.status = "failed"
    call.tenant_id = ctx.tenant_id
    call.agent_id = agent_id
    call.query_preview = "失败场景问题"
    call.answer_preview = ""
    call.conversation_id = None
    call.trace_id = None
    call.created_at = datetime.now(UTC)

    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = call
    db.execute = AsyncMock(return_value=result)
    db.scalar = AsyncMock(return_value=-1)
    db.add = MagicMock()
    db.flush = AsyncMock()

    row = await promote_case_from_call(
        db,
        ctx,
        dataset_id=uuid4(),
        agent_id=agent_id,
        call_id=call_id,
    )
    assert row.query == "失败场景问题"
    assert "contains" not in row.expected
    assert row.expected["_source"]["call_status"] == "failed"
    assert row.name.startswith("[failed]")


@pytest.mark.asyncio
async def test_promote_success_default_contains():
    ctx = SimpleNamespace(tenant_id=uuid4(), user_id=uuid4(), is_superuser=False)
    agent_id = uuid4()
    call_id = uuid4()
    call = MagicMock()
    call.id = call_id
    call.status = "success"
    call.tenant_id = ctx.tenant_id
    call.agent_id = agent_id
    call.query_preview = "用户问题全文够长吗"
    call.answer_preview = "助手答案"
    call.conversation_id = None
    call.trace_id = "tr-1"
    call.created_at = datetime.now(UTC)

    db = AsyncMock()
    call_result = MagicMock()
    call_result.scalar_one_or_none.return_value = call
    db.execute = AsyncMock(return_value=call_result)
    db.scalar = AsyncMock(return_value=2)
    db.add = MagicMock()
    db.flush = AsyncMock()

    row = await promote_case_from_call(
        db,
        ctx,
        dataset_id=uuid4(),
        agent_id=agent_id,
        call_id=call_id,
    )
    assert row.query == "用户问题全文够长吗"
    assert row.expected["contains"] == "助手答案"
    assert row.expected["_source"]["call_id"] == str(call_id)
    assert row.sort_index == 3
    db.add.assert_called_once()
