"""生成模型默认选取（厂商优先级）。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.integrations.generative.registry import (
    default_image_invoke_mode,
    default_video_invoke_mode,
)
from app.models.model import ModelConfig
from app.models.model.catalog import ModelCapabilityType, ModelVendor
from app.tenant.models.services import generative_model_resolve as gm
from uuid import uuid4


def _model(vendor: str, model_type: str) -> ModelConfig:
    return ModelConfig(
        id=uuid4(),
        tenant_id=uuid4(),
        name=vendor,
        provider=vendor,
        model_name="m",
        model_code="m",
        vendor=vendor,
        model_type=model_type,
        extra={},
    )


def test_default_video_invoke_mode_qwen_first():
    assert default_video_invoke_mode(_model(ModelVendor.QWEN.value, ModelCapabilityType.VIDEO_GEN.value)) == "dashscope_t2v"
    assert default_video_invoke_mode(_model(ModelVendor.DOUBAO.value, ModelCapabilityType.VIDEO_GEN.value)) == "volcengine_video"
    assert default_video_invoke_mode(_model(ModelVendor.OPENAI.value, ModelCapabilityType.VIDEO_GEN.value)) == "dashscope_t2v"


def test_default_image_invoke_mode_qwen_vs_openai():
    assert default_image_invoke_mode(_model(ModelVendor.QWEN.value, ModelCapabilityType.IMAGE_GEN.value)) == "dashscope_t2i"
    assert default_image_invoke_mode(_model(ModelVendor.OPENAI.value, ModelCapabilityType.IMAGE_GEN.value)) == "openai_images"


def _run(coro):
    return asyncio.run(coro)


def _async_db(row=None):
    """mock 异步会话：db.execute 返回 Result，scalar_one_or_none 命中 row。"""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    db.execute.return_value = result
    return db


def test_image_resolve_prefers_explicit_id_over_agent_model(monkeypatch):
    explicit = _model(ModelVendor.QWEN.value, ModelCapabilityType.IMAGE_GEN.value)
    agent_model = _model(ModelVendor.DOUBAO.value, ModelCapabilityType.IMAGE_GEN.value)
    seen: list = []

    async def fake_resolve(_db, model, _tenant_id):
        seen.append(model.id)
        return model

    monkeypatch.setattr(gm, "resolve_model_for_invoke", fake_resolve)

    async def forbidden_default(**kwargs):
        raise AssertionError("显式 id 命中后不应再取默认模型")

    monkeypatch.setattr(gm, "pick_default_generative_model", forbidden_default)
    ctx = SimpleNamespace(tenant_id=uuid4())

    db = _async_db(row=explicit)
    out = _run(gm.resolve_image_gen_model(db, ctx, model_config_id=explicit.id, agent_model=agent_model))
    assert out is explicit
    assert seen == [explicit.id]


def test_image_resolve_falls_back_to_agent_model(monkeypatch):
    agent_model = _model(ModelVendor.QWEN.value, ModelCapabilityType.IMAGE_GEN.value)
    seen: list = []

    async def fake_resolve(_db, model, _tenant_id):
        seen.append(model.id)
        return model

    monkeypatch.setattr(gm, "resolve_model_for_invoke", fake_resolve)

    async def forbidden_default(**kwargs):
        raise AssertionError("agent 绑定模型命中后不应再取默认")

    monkeypatch.setattr(gm, "pick_default_generative_model", forbidden_default)
    ctx = SimpleNamespace(tenant_id=uuid4())

    db = _async_db()  # 无显式 id，不应执行 SELECT
    out = _run(gm.resolve_image_gen_model(db, ctx, model_config_id=None, agent_model=agent_model))
    assert out is agent_model
    assert seen == [agent_model.id]


def test_video_resolve_falls_back_to_tenant_default(monkeypatch):
    wrong = _model(ModelVendor.DOUBAO.value, ModelCapabilityType.IMAGE_GEN.value)  # agent 绑 image_gen，与 video_gen 不匹配
    default_row = _model(ModelVendor.QWEN.value, ModelCapabilityType.VIDEO_GEN.value)
    seen: list = []

    async def fake_resolve(_db, model, _tenant_id):
        seen.append(model.id)
        return model

    monkeypatch.setattr(gm, "resolve_model_for_invoke", fake_resolve)

    async def pick_default(**kwargs):
        return default_row

    monkeypatch.setattr(gm, "pick_default_generative_model", pick_default)
    ctx = SimpleNamespace(tenant_id=uuid4())

    db = _async_db()
    out = _run(gm.resolve_video_gen_model(db, ctx, model_config_id=None, agent_model=wrong))
    assert out is default_row
    assert seen == [default_row.id]


def test_image_resolve_prefers_agent_config_default_over_agent_model(monkeypatch):
    cfg_model = _model(ModelVendor.QWEN.value, ModelCapabilityType.IMAGE_GEN.value)
    agent_model = _model(ModelVendor.DOUBAO.value, ModelCapabilityType.IMAGE_GEN.value)
    seen: list = []

    async def fake_resolve(_db, model, _tenant_id):
        seen.append(model.id)
        return model

    monkeypatch.setattr(gm, "resolve_model_for_invoke", fake_resolve)

    async def forbidden_default(**kwargs):
        raise AssertionError("agent_config 默认 id 落入显式 id 分支后不应再取默认模型")

    monkeypatch.setattr(gm, "pick_default_generative_model", forbidden_default)
    ctx = SimpleNamespace(tenant_id=uuid4())

    db = _async_db(row=cfg_model)
    out = _run(
        gm.resolve_image_gen_model(
            db,
            ctx,
            model_config_id=None,
            agent_model=agent_model,
            agent_config={"generative_image_model_id": str(cfg_model.id)},
        )
    )
    assert out is cfg_model
    assert seen == [cfg_model.id]
