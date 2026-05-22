"""流程画布 RAG 节点：检索与 prompt 拼装（调用 L2 rag.generate）。"""

from typing import Any
from uuid import UUID

from app.rag.generate import format_hits_context, retrieve_hits
from app.flow_runtime.types import RunContext


async def knowledge_search(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> list[dict[str, Any]]:
    query = str(inputs.get("query") or inputs.get("input") or "")
    if not query:
        return []
    kb_id = node_data.get("kb_id")
    top_k = int(node_data.get("top_k") or 5)
    kb_ids = [str(kb_id)] if kb_id else ctx.kb_ids
    from app.infra.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return await retrieve_hits(
            query,
            tenant_id=UUID(ctx.tenant_id),
            kb_ids=kb_ids,
            db=db,
            top_k=top_k,
        )


async def prompt_template(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    template = node_data.get("template") or (
        "基于以下检索结果回答问题：\n\n{{检索结果}}\n\n问题：{{用户提问}}"
    )
    query = str(inputs.get("query") or ctx.inputs.get("query", ""))
    hits = inputs.get("hits") or inputs.get("检索结果") or []
    if isinstance(hits, list) and hits and isinstance(hits[0], dict):
        context = format_hits_context(hits)
    else:
        context = str(hits)
    result = template.replace("{{用户提问}}", query).replace("{{query}}", query)
    result = result.replace("{{检索结果}}", context).replace("{{context}}", context)
    if ctx.system_prompt:
        result = f"{ctx.system_prompt}\n\n{result}"
    return result
