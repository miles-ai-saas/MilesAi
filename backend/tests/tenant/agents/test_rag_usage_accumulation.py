"""回归：RAG 图节点内写入的用量累计必须回到调用方上下文。

``AgentChatCall`` 的 token 来自 ``_chat_usage_acc`` ContextVar，而 ``ModelUsageLog``
行由会话写入。若累计写成「每次 ``ContextVar.set()`` 新值」，LangGraph 在子 task 中
执行节点时父 context 读不到写入，就会出现「有日志、无汇总」（token 恒为 0）——本
测试用真实编译图（仅替换会话工厂、检索与 LLM）钉住「节点内写入必须回到调用方」。
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import miles_ai.integrations.langgraph.graphs.rag_qa as rag_qa
import miles_ai.rag.generate.answer as answer_mod
from miles_ai.integrations.langgraph.graphs.rag_qa import build_rag_qa_graph
from miles_portal.tenant.models.services.usage import (
    UsageRecordContext,
    begin_chat_usage_accumulation,
    end_chat_usage_accumulation,
    get_chat_usage_totals,
    record_model_usage,
)


class _FakeDb:
    """record_model_usage 只需要 add() 与 flush()。"""

    def __init__(self) -> None:
        self.rows: list[object] = []

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def flush(self) -> None:
        return None


class _ShortSession:
    """short_db_session 替身：retrieve 节点会开短会话。"""

    async def __aenter__(self) -> "_ShortSession":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


async def test_graph_node_usage_reaches_caller_contextvar(monkeypatch):
    tenant_id = uuid4()
    db = _FakeDb()
    model = AsyncMock()
    model.id = uuid4()
    model.name = "m"

    async def fake_record(*, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        await record_model_usage(
            UsageRecordContext(
                db=db,
                tenant_id=tenant_id,
                model=model,
                source="chat",
                source_id=uuid4(),
            ),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    sink = AsyncMock()
    sink.record = AsyncMock(side_effect=fake_record)

    async def fake_ainvoke(_model, _messages, **kwargs):
        # 真实 adapter 在 LLM 返回后调 sink.record；必须复刻，否则测试无效
        if kwargs.get("usage_sink") is not None:
            await kwargs["usage_sink"].record(prompt_tokens=7, completion_tokens=3)
        return "答案"

    monkeypatch.setattr(rag_qa, "short_db_session", _ShortSession)
    monkeypatch.setattr(rag_qa, "retrieve_hits", AsyncMock(return_value=[{"content": "片段", "score": 0.9}]))
    monkeypatch.setattr(answer_mod, "ainvoke_chat", AsyncMock(side_effect=fake_ainvoke))

    initial = {
        "query": "问题",
        "prompt_query": "问题",
        "system_prompt": "sys",
        "kb_ids": ["kb1"],
        "tenant_id": str(tenant_id),
        "top_k": 5,
        "temperature": 0.7,
        "max_retries": 1,
        "retry_count": 0,
        "relevance_threshold": 0.35,
        "use_llm_grade": False,
        "media": [],
        "agent_id": str(uuid4()),
        "hits": [],
        "steps": [],
    }
    config = {"configurable": {"model": model, "usage_sink": sink, "kb_retrieval": object()}}

    token = begin_chat_usage_accumulation()
    try:
        await build_rag_qa_graph().compile().ainvoke(initial, config)
        totals = get_chat_usage_totals()
    finally:
        end_chat_usage_accumulation(token)

    # 探针有效性：图内 sink 必须真的记录过，否则本测试不能证明任何事情
    assert db.rows, "sink.record 未被调用，测试无效"
    assert totals == (7, 3), (
        "图节点内写入的 chat 用量必须回到调用方；若为 (0, 0)，说明累计又退回「重新绑定 ContextVar」的写法（见 usage.py 的 ChatUsageAccumulator 说明）。"
    )
