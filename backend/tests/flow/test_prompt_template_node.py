"""画布 PromptTemplate 节点：内联模板与模板库 live 引用（经 RunContext 回调注入）。"""

from uuid import UUID, uuid4

import pytest

from miles_ai.flow_runtime.nodes import rag_nodes
from miles_ai.flow_runtime.types import RunContext
from miles_common.exceptions import BadRequestError


class _RecordingShortSession:
    """假 AsyncSessionLocal：记录开合次数并交出可辨识的 db。"""

    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> "_RecordingShortSession":
        self.entered += 1
        return self

    async def __aexit__(self, *exc: object) -> bool:
        self.exited += 1
        return False


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


@pytest.mark.asyncio
async def test_knowledge_search_retrieves_on_its_own_session(monkeypatch):
    """KnowledgeSearch 站点：检索在自开的一次会话上进行，参数与结果原样透出。"""
    short = _RecordingShortSession()
    monkeypatch.setattr(rag_nodes, "AsyncSessionLocal", lambda: short)

    seen = []

    async def fake_retrieve_hits(query, *, tenant_id, kb_ids, db, top_k, mode, bindings):
        seen.append((query, tenant_id, kb_ids, db, top_k, mode, bindings))
        return [{"content": "片段", "score": 0.8}]

    monkeypatch.setattr(rag_nodes, "retrieve_hits", fake_retrieve_hits)

    tenant_id = str(uuid4())
    bindings = object()
    ctx = RunContext(tenant_id=tenant_id, kb_ids=["kb-default"], kb_retrieval=bindings)

    out = await rag_nodes.knowledge_search(
        {"kb_id": "kb-node", "top_k": 7, "retrieval_mode": "hybrid"},
        {"query": "问题"},
        ctx,
    )

    assert out == [{"content": "片段", "score": 0.8}]
    assert len(seen) == 1
    query, passed_tenant_id, kb_ids, db, top_k, mode, passed_bindings = seen[0]
    assert query == "问题"
    assert passed_tenant_id == UUID(tenant_id)
    assert kb_ids == ["kb-node"]
    assert isinstance(db, _RecordingShortSession)
    assert db is short
    assert (top_k, mode) == (7, "hybrid")
    assert passed_bindings is bindings
    assert (short.entered, short.exited) == (1, 1)
