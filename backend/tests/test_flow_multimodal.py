"""流程 LLMCall 多模态与 FlowRunRequest。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError
from app.common.schemas.media import MediaRefIn
from app.flow_runtime.context_utils import media_refs_from_run
from app.flow_runtime.nodes.llm_nodes import llm_call
from app.flow_runtime.types import RunContext
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
    ctx = RunContext(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        inputs={"query": "描述图片"},
        model_config_id=str(model_id),
        media=[{"attachment_id": str(att_id), "detail": "auto"}],
        permissions=frozenset(),
    )
    model_row = SimpleNamespace(
        id=model_id,
        name="vision",
        model_type="vision",
        is_active=True,
    )
    mock_msg = {
        "role": "user",
        "content": [
            {"type": "text", "text": "描述图片"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}},
        ],
    }

    with (
        patch("app.flow_runtime.nodes.llm_nodes.AsyncSessionLocal") as session_cls,
        patch(
            "app.flow_runtime.nodes.llm_nodes.resolve_model_for_invoke",
            new_callable=AsyncMock,
            return_value=model_row,
        ),
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
        db = MagicMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=model_row))
        )
        session_cls.return_value.__aenter__ = AsyncMock(return_value=db)
        session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        out = await llm_call({}, {"prompt": "描述图片"}, ctx)

    assert out == "ok"
    mock_chat.assert_awaited_once()
    sent_messages = mock_chat.await_args.args[1]
    user = sent_messages[-1]
    assert isinstance(user["content"], list)


@pytest.mark.asyncio
async def test_llm_call_no_input_raises():
    ctx = RunContext(tenant_id=str(uuid4()), user_id=str(uuid4()))
    with pytest.raises(BadRequestError, match="缺少输入"):
        await llm_call({}, {}, ctx)
