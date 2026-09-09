"""flow_run_context 装配：settings 门控 submit_generative_* 注入（B-2e 防回归）。

B-2e 起画布生图/生视频节点按 ``RunContext.submit_generative_* is not None``
判定是否异步入队（None ⇒ 节点落同步 resolver 兜底）；根装配点必须在
settings ``generative_*_async`` 关闭时不注入、开启时注入 L1 提交回调。
本测试固化该不变式，防未来新增装配点遗漏。
"""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.tenant.agents.services.agent import chat_rag as chat_rag_mod
from app.tenant.agents.services.agent.chat_rag import AgentChatRagMixin


def _run(coro):
    return asyncio.run(coro)


def _make_service() -> SimpleNamespace:
    async def resolve_system_prompt(agent):
        return "system-prompt"

    return SimpleNamespace(
        ctx=SimpleNamespace(
            tenant_id=uuid4(),
            user_id=uuid4(),
            permissions=frozenset(["agent:chat"]),
            is_superuser=False,
        ),
        resolve_system_prompt=resolve_system_prompt,
    )


def _make_agent() -> SimpleNamespace:
    return SimpleNamespace(
        model_config_id=uuid4(),
        tenant_id=uuid4(),
        config={},
    )


def _flow_context(svc) -> dict:
    return _run(
        AgentChatRagMixin.flow_run_context(
            svc,
            _make_agent(),
            agent_id=uuid4(),
            inputs={"query": "hi"},
            kb_ids=[],
        )
    )


def test_flow_run_context_injects_resolvers_and_bindings_always():
    """与 settings 无关的注入（resolver/KB/usage）恒定存在。"""
    ctx = _flow_context(_make_service())
    assert ctx.resolve_generative_image is chat_rag_mod.resolve_image_gen_model
    assert ctx.resolve_generative_video is chat_rag_mod.resolve_video_gen_model
    assert callable(ctx.resolve_model)
    assert ctx.kb_retrieval is not None
    assert ctx.usage_sink is None


def test_flow_run_context_injects_submitters_when_async_enabled(monkeypatch):
    monkeypatch.setattr(chat_rag_mod.GenerativeJobService, "image_async_enabled", lambda: True)
    monkeypatch.setattr(chat_rag_mod.GenerativeJobService, "video_async_enabled", lambda: True)
    ctx = _flow_context(_make_service())
    assert ctx.submit_generative_image is chat_rag_mod.submit_generative_image_job
    assert ctx.submit_generative_video is chat_rag_mod.submit_generative_video_job


def test_flow_run_context_skips_submitters_when_async_disabled(monkeypatch):
    monkeypatch.setattr(chat_rag_mod.GenerativeJobService, "image_async_enabled", lambda: False)
    monkeypatch.setattr(chat_rag_mod.GenerativeJobService, "video_async_enabled", lambda: False)
    ctx = _flow_context(_make_service())
    # settings 关闭 ⇒ None ⇒ 节点落同步 resolver 兜底（不产生生成任务）
    assert ctx.submit_generative_image is None
    assert ctx.submit_generative_video is None
    # 同步 resolver 注入不受 settings 影响，同步兜底始终可用
    assert ctx.resolve_generative_image is not None
    assert ctx.resolve_generative_video is not None
