"""EvalService：创建 run 与启动派发。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_common.schema import PageParams
from miles_core.models.eval import EvalRunStatus
from miles_portal.tenant.eval.schemas.eval import EvalCaseCreate, EvalDatasetCreate, EvalRunCreate
from miles_portal.tenant.eval.services.eval_service import EvalService


def _ctx(tenant_id=None, user_id=None):
    return SimpleNamespace(
        tenant_id=tenant_id or uuid4(),
        user_id=user_id or uuid4(),
        permissions=frozenset(["agent:read", "agent:write"]),
        is_superuser=False,
    )


@pytest.mark.asyncio
async def test_create_run_requires_cases():
    db = AsyncMock()
    ctx = _ctx()
    ds_id, agent_id = uuid4(), uuid4()

    dataset = SimpleNamespace(
        id=ds_id,
        tenant_id=ctx.tenant_id,
        deleted_at=None,
        name="ds",
        description=None,
        created_at=MagicMock(),
    )
    agent = SimpleNamespace(id=agent_id, tenant_id=ctx.tenant_id, deleted_at=None)

    async def fake_get(model, pk):  # noqa: ANN001
        if model.__name__ == "EvalDataset":
            return dataset
        if model.__name__ == "Agent":
            return agent
        return None

    db.get = AsyncMock(side_effect=fake_get)
    db.scalar = AsyncMock(return_value=0)

    with pytest.raises(BadRequestError, match="没有用例"):
        await EvalService(db, ctx).create_run(
            EvalRunCreate(dataset_id=ds_id, agent_id=agent_id),
        )


@pytest.mark.asyncio
async def test_start_run_sends_celery_task():
    db = AsyncMock()
    ctx = _ctx()
    run_id = uuid4()
    run = SimpleNamespace(
        id=run_id,
        tenant_id=ctx.tenant_id,
        status=EvalRunStatus.PENDING.value,
        error_message=None,
        dataset_id=uuid4(),
        agent_id=uuid4(),
        scoring_mode="auto",
        started_at=None,
        finished_at=None,
        summary={},
        created_at=MagicMock(),
    )
    db.get = AsyncMock(return_value=run)
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with patch("miles_portal.tenant.eval.services.eval_service.celery_app") as celery:
        celery.send_task = MagicMock()
        out = await EvalService(db, ctx).start_run(run_id)

    celery.send_task.assert_called_once()
    assert out.id == run_id
    assert run.status == EvalRunStatus.PENDING.value
