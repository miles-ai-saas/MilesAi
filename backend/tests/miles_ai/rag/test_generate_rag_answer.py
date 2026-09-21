"""无 db 的生成入口：签名不变量 + prompt 构造 + 附图错误语义。

生成阶段要释放连接，靠的是「生成函数拿不到 db」这个签名级约束；本文件把
签名钉住，并覆盖 prompt 构造的两种分支与缺 media_reader 的显式报错。
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_ai.rag.generate.answer import build_rag_prompt, generate_rag_answer
from miles_common.exceptions import BadRequestError
from miles_common.schemas.media import MediaRefIn


def test_generate_rag_answer_signature_has_no_db():
    params = inspect.signature(generate_rag_answer).parameters
    assert "db" not in params
    assert "kb_ids" not in params
    assert "tenant_id" not in params
    assert "bindings" not in params


def test_build_rag_prompt_without_hits_uses_system_and_question():
    prompt = build_rag_prompt(system_prompt="你是助手", query="问题", hits=[])
    assert prompt == "你是助手\n\n用户问题：问题"


def test_build_rag_prompt_with_hits_includes_context():
    prompt = build_rag_prompt(
        system_prompt="你是助手",
        query="问题",
        hits=[{"content_preview": "片段", "score": 0.9}],
    )
    assert "你是助手" in prompt
    assert "片段" in prompt
    assert prompt.endswith("问题")


@pytest.mark.asyncio
async def test_generate_rag_answer_passes_prompt_and_forwards_on_delta():
    async def delta(_: str) -> None:
        pass

    usage_sink = object()
    with patch(
        "miles_ai.rag.generate.answer.ainvoke_chat",
        new_callable=AsyncMock,
        return_value="答",
    ) as mock_chat:
        answer = await generate_rag_answer(
            model=MagicMock(),
            prompt="拼好的 prompt",
            temperature=0.3,
            on_delta=delta,
            usage_sink=usage_sink,
        )

    assert answer == "答"
    assert mock_chat.await_args.args[1] == [{"role": "user", "content": "拼好的 prompt"}]
    assert mock_chat.await_args.kwargs["temperature"] == 0.3
    assert mock_chat.await_args.kwargs["on_delta"] is delta
    assert mock_chat.await_args.kwargs["usage_sink"] is usage_sink


@pytest.mark.asyncio
async def test_generate_rag_answer_with_media_without_reader_raises():
    with pytest.raises(BadRequestError, match="media_reader"):
        await generate_rag_answer(
            model=MagicMock(),
            prompt="p",
            media=[MediaRefIn(attachment_id=uuid4())],
        )


@pytest.mark.asyncio
async def test_generate_rag_answer_resolves_media_before_llm():
    reader = MagicMock()
    with (
        patch(
            "miles_ai.rag.generate.answer.build_invoke_messages_with_media",
            new_callable=AsyncMock,
            return_value=[{"role": "user", "content": [{"type": "text", "text": "x"}]}],
        ) as mock_build,
        patch(
            "miles_ai.rag.generate.answer.ainvoke_chat",
            new_callable=AsyncMock,
            return_value="答",
        ),
    ):
        await generate_rag_answer(
            model=MagicMock(),
            prompt="p",
            media=[MediaRefIn(attachment_id=uuid4())],
            media_reader=reader,
        )

    assert mock_build.await_args.args[0] is reader
    assert mock_build.await_args.kwargs["prompt_text"] == "p"
