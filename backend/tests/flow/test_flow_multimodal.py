"""流程 LLMCall 多模态与 FlowRunRequest。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError
from app.common.schemas.media import MediaRefIn
from app.flow_runtime.context_utils import media_refs_from_run
from app.flow_runtime.nodes.llm_nodes import llm_call
from app.flow_runtime.types import RunContext
from app.integrations.langgraph.compiler import run_compiled_canvas
from app.models.model import ModelConfig
from app.tenant.flows.schemas.flow import FlowRunRequest


def test_flow_run_request_media_only():
    body = FlowRunRequest(inputs={}, media=[MediaRefIn(attachment_id=uuid4())])
    assert len(body.media) == 1


def test_flow_run_request_requires_query_or_media():
    with pytest.raises(ValueError, match="query"):
        FlowRunRequest(inputs={})


def test_media_refs_from_run():
    aid = uuid4()
    ctx = RunContext(
        tenant_id=str(uuid4()),
        media=[{"attachment_id": str(aid), "detail": "auto"}],
    )
    refs = media_refs_from_run(ctx)
    assert len(refs) == 1
    assert refs[0].attachment_id == aid


@pytest.mark.asyncio
async def test_llm_call_with_media_builds_multimodal_message():
    tenant_id = uuid4()
    user_id = uuid4()
    att_id = uuid4()
    model_id = uuid4()
    model_row = SimpleNamespace(
        id=model_id,
        name="vision",
        model_type="vision",
        is_active=True,
    )

    async def fake_resolve(model_id: str):
        return model_row

    usage_sink = object()
    sink_models: list[object] = []

    def sink_factory(model):
        sink_models.append(model)
        return usage_sink

    ctx = RunContext(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        inputs={"query": "描述图片"},
        model_config_id=str(model_id),
        media=[{"attachment_id": str(att_id), "detail": "auto"}],
        permissions=frozenset(),
        resolve_model=fake_resolve,
        usage_sink_factory=sink_factory,
        media_reader=object(),
    )
    mock_msg = {
        "role": "user",
        "content": [
            {"type": "text", "text": "描述图片"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}},
        ],
    }

    with (
        patch(
            "app.flow_runtime.nodes.llm_nodes.resolve_media_refs",
            new_callable=AsyncMock,
            return_value=mock_msg["content"][1:],
        ),
        patch(
            "app.flow_runtime.nodes.llm_nodes.ainvoke_chat",
            new_callable=AsyncMock,
            return_value="ok",
        ) as mock_chat,
    ):
        out = await llm_call({}, {"prompt": "描述图片"}, ctx)

    assert out == "ok"
    mock_chat.assert_awaited_once()
    sent_messages = mock_chat.await_args.args[1]
    user = sent_messages[-1]
    assert isinstance(user["content"], list)
    assert mock_chat.await_args.kwargs["usage_sink"] is usage_sink
    assert sink_models == [model_row]


@pytest.mark.asyncio
async def test_llm_call_with_media_without_reader_raises():
    """附图运行未装配 media_reader 时必须显式报错，而非静默忽略图片。"""
    model_row = SimpleNamespace(id=uuid4(), name="vision", model_type="vision", is_active=True)

    async def fake_resolve(model_id: str):
        return model_row

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        inputs={"query": "看图"},
        model_config_id=str(uuid4()),
        media=[{"attachment_id": str(uuid4()), "detail": "auto"}],
        resolve_model=fake_resolve,
    )

    with pytest.raises(BadRequestError, match="媒体读取器"):
        await llm_call({}, {"prompt": "看图"}, ctx)


@pytest.mark.asyncio
async def test_llm_call_no_input_raises():
    ctx = RunContext(tenant_id=str(uuid4()), user_id=str(uuid4()))
    with pytest.raises(BadRequestError, match="缺少输入"):
        await llm_call({}, {}, ctx)


@pytest.mark.asyncio
async def test_run_compiled_canvas_forwards_resolver_and_usage_sink():
    """编译画布端到端回归：LLMCall 经 ctx.resolve_model 解析，usage_sink 透传到 ainvoke_chat。

    ``run_compiled_canvas`` 把 ctx.resolve_model / ctx.usage_sink_factory 写入 graph state，
    节点层（``llm_nodes.llm_call``）从子 RunContext 读取后调用；此处用假回调/假 sink
    固定该注入链，防止回归到节点自行查库。
    """
    tenant_id = uuid4()
    model_id = uuid4()
    model = ModelConfig(name="推理", provider="openai", model_name="gpt-4o-mini")
    resolved_ids: list[str] = []
    usage_sink = object()

    def sink_factory(model):
        return usage_sink

    async def fake_resolve(model_config_id: str):
        resolved_ids.append(model_config_id)
        return model

    graph = {
        "nodes": [
            {
                "id": "in_1",
                "type": "TextInput",
                "data": {"type": "TextInput", "input_key": "query", "label": "输入"},
            },
            {
                "id": "llm_1",
                "type": "LLMCall",
                "data": {
                    "type": "LLMCall",
                    "model_config_id": str(model_id),
                    "temperature": 0.7,
                    "label": "大模型",
                },
            },
            {
                "id": "out_1",
                "type": "TextOutput",
                "data": {"type": "TextOutput", "label": "输出"},
            },
        ],
        "edges": [
            {
                "id": "e1",
                "source": "in_1",
                "target": "llm_1",
                "sourceHandle": "output",
                "targetHandle": "query",
            },
            {
                "id": "e2",
                "source": "llm_1",
                "target": "out_1",
                "sourceHandle": "output",
                "targetHandle": "input",
            },
        ],
    }
    ctx = RunContext(
        tenant_id=str(tenant_id),
        user_id=str(uuid4()),
        inputs={"query": "画布链路测试"},
        resolve_model=fake_resolve,
        usage_sink_factory=sink_factory,
    )

    with patch(
        "app.flow_runtime.nodes.llm_nodes.ainvoke_chat",
        new_callable=AsyncMock,
        return_value="ok",
    ) as mock_chat:
        output, steps = await run_compiled_canvas(graph, ctx)

    assert output == "ok"
    assert resolved_ids == [str(model_id)]
    assert any(s.get("node_type") == "LLMCall" for s in steps if isinstance(s, dict))
    mock_chat.assert_awaited_once()
    assert mock_chat.await_args.args[0] is model
    assert mock_chat.await_args.kwargs["usage_sink"] is usage_sink
