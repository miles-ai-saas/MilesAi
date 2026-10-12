"""模型目录 M4：下架引用校验、批量导入、icon 写入 extra。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from miles_admin.app_ops.schemas.model_catalog import (
    ModelCatalogImportBody,
    ModelCatalogImportItem,
)
from miles_admin.app_ops.services.model_catalog import AdminModelCatalogService, _admin_out
from miles_common.exceptions import ConflictError
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelPublishStatus


def _builtin(**kwargs) -> ModelConfig:
    defaults = {
        "id": uuid4(),
        "tenant_id": None,
        "name": "Demo",
        "vendor": "deepseek",
        "provider": "deepseek",
        "model_name": "deepseek-chat",
        "model_code": "deepseek-chat",
        "model_type": "llm",
        "description": None,
        "context_window": None,
        "badge": None,
        "sort_order": 0,
        "is_featured": False,
        "publish_status": ModelPublishStatus.PUBLISHED.value,
        "is_active": True,
        "api_base": None,
        "api_key_encrypted": None,
        "extra": {},
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    m = MagicMock(spec=ModelConfig)
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def test_admin_out_reads_icon_from_extra():
    m = _builtin(extra={"icon": "https://cdn.example/qwen.png"})
    out = _admin_out(m)
    assert out.icon == "https://cdn.example/qwen.png"


@pytest.mark.asyncio
async def test_deprecate_blocked_when_referenced():
    model_id = uuid4()
    m = _builtin(id=model_id)
    db = AsyncMock()
    svc = AdminModelCatalogService(db)
    svc._get_builtin = AsyncMock(return_value=m)

    async def _scalar(stmt):
        # agents then kbs
        if not hasattr(_scalar, "n"):
            _scalar.n = 0
        _scalar.n += 1
        return 2 if _scalar.n == 1 else 1

    db.scalar = AsyncMock(side_effect=_scalar)

    with pytest.raises(ConflictError, match="智能体"):
        await svc.deprecate(model_id, force=False)


@pytest.mark.asyncio
async def test_deprecate_force_when_referenced():
    model_id = uuid4()
    m = _builtin(id=model_id)
    db = AsyncMock()
    svc = AdminModelCatalogService(db)
    svc._get_builtin = AsyncMock(return_value=m)
    db.scalar = AsyncMock(side_effect=[3, 0])
    db.flush = AsyncMock()

    out = await svc.deprecate(model_id, force=True)
    assert m.publish_status == ModelPublishStatus.DEPRECATED.value
    assert m.is_active is False
    assert out.publish_status == ModelPublishStatus.DEPRECATED.value


@pytest.mark.asyncio
async def test_import_creates_and_upserts():
    db = AsyncMock()
    svc = AdminModelCatalogService(db)

    existing = _builtin(model_code="keep-me", name="Old")
    # first item: no existing; second: existing
    execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=existing)),
    ]
    db.execute = AsyncMock(side_effect=execute_results)
    db.flush = AsyncMock()
    db.add = MagicMock()

    body = ModelCatalogImportBody(
        items=[
            ModelCatalogImportItem(
                name="New Model",
                vendor="qwen",
                model_name="qwen-plus",
                model_code="qwen-plus-new",
                icon="qwen",
            ),
            ModelCatalogImportItem(
                name="Renamed",
                vendor="deepseek",
                model_name="deepseek-chat",
                model_code="keep-me",
                publish_status="published",
            ),
        ],
        upsert=True,
    )
    result = await svc.import_catalog(body)
    assert result.created == 1
    assert result.updated == 1
    assert result.skipped == 0
    assert existing.name == "Renamed"
    db.add.assert_called_once()
