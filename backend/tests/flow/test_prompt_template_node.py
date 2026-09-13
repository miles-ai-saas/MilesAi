"""画布 PromptTemplate 节点：内联模板与模板库 live 引用（经 RunContext 回调注入）。"""

from uuid import uuid4

import pytest

from miles_ai.flow_runtime.nodes import rag_nodes
from miles_ai.flow_runtime.types import RunContext
from miles_common.exceptions import BadRequestError


def test_apply_prompt_placeholders():
    out = rag_nodes._apply_prompt_placeholders(
        "Q={{用户提问}} C={{检索结果}}",
        query="hello",
        hits=[{"content": "doc-a", "score": 0.9}],
    )
    assert "hello" in out
    assert "0.90" in out


@pytest.mark.asyncio
async def test_prompt_template_inline():
    ctx = RunContext(tenant_id=str(uuid4()))
    out = await rag_nodes.prompt_template(
        {"template": "问题：{{用户提问}}"},
        {"query": "测试"},
        ctx,
    )
    assert out == "问题：测试"


@pytest.mark.asyncio
async def test_prompt_template_live_reference():
    tenant_id = str(uuid4())
    template_id = str(uuid4())
    live_content = "LIVE {{用户提问}} / {{检索结果}}"

    async def _fake_resolve(prompt_template_id: str, tid: str) -> str | None:
        assert prompt_template_id == template_id
        assert tid == tenant_id
        return live_content

    ctx = RunContext(tenant_id=tenant_id, resolve_prompt_template=_fake_resolve)
    out = await rag_nodes.prompt_template(
        {
            "prompt_template_id": template_id,
            "template": "内联应被忽略",
        },
        {"query": "q1", "hits": []},
        ctx,
    )
    assert out.startswith("LIVE q1")


@pytest.mark.asyncio
async def test_prompt_template_live_reference_fallback_to_inline():
    tenant_id = str(uuid4())

    async def _missing(_prompt_template_id: str, _tid: str) -> str | None:
        return None

    ctx = RunContext(tenant_id=tenant_id, resolve_prompt_template=_missing)
    out = await rag_nodes.prompt_template(
        {
            "prompt_template_id": str(uuid4()),
            "template": "备用 {{用户提问}}",
        },
        {"query": "fallback"},
        ctx,
    )
    assert out == "备用 fallback"


@pytest.mark.asyncio
async def test_prompt_template_live_reference_without_callback_raises():
    ctx = RunContext(tenant_id=str(uuid4()))
    with pytest.raises(BadRequestError, match="prompt 模板解析回调"):
        await rag_nodes.prompt_template(
            {
                "prompt_template_id": str(uuid4()),
                "template": "内联不救 live 引用",
            },
            {"query": "q"},
            ctx,
        )

    # 无回调 + 无 prompt_template_id：inline template 照常渲染，不报错
    ctx_inline = RunContext(tenant_id=str(uuid4()))
    out = await rag_nodes.prompt_template(
        {"template": "问题：{{用户提问}}"},
        {"query": "内联ok"},
        ctx_inline,
    )
    assert out == "问题：内联ok"


@pytest.mark.asyncio
async def test_prompt_template_prepends_system_prompt():
    ctx = RunContext(tenant_id=str(uuid4()), system_prompt="你是助手")
    out = await rag_nodes.prompt_template(
        {"template": "答：{{用户提问}}"},
        {"query": "hi"},
        ctx,
    )
    assert out.startswith("你是助手\n\n答：hi")
