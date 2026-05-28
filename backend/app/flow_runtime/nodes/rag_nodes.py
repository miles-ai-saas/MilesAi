"""
流程画布 RAG 节点（L2 能力复用）。

节点类型
--------
- **KnowledgeSearch**：``retrieve_hits`` → hit 列表（与 Agent RAG 同检索链，不写 search_log）
- **PromptTemplate**：``format_hits_context`` + 占位符模板 → 下游 **LLMCall** 的 prompt 字符串

知识库来源
----------
1. 节点 ``data.kb_id`` 指定单库（优先）
2. 否则使用 ``RunContext.kb_ids``（Agent 发布流程对话时由 ``AgentService`` 注入）

会话：节点内 ``AsyncSessionLocal`` 独立开库，避免与外层 HTTP 事务纠缠。
"""

from typing import Any
from uuid import UUID

from app.core.soft_delete import is_marked_deleted
from app.infra.db import AsyncSessionLocal
from app.rag.generate import format_hits_context, retrieve_hits
from app.flow_runtime.types import RunContext
from app.tenant.prompts.models import PromptTemplate

_DEFAULT_PROMPT_TEMPLATE = "基于以下检索结果回答问题：\n\n{{检索结果}}\n\n问题：{{用户提问}}"


async def knowledge_search(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> list[dict[str, Any]]:
    """画布 KnowledgeSearch：多 KB retrieve_hits。"""
    query = str(inputs.get("query") or inputs.get("input") or "")
    if not query:
        return []
    kb_id = node_data.get("kb_id")
    top_k = int(node_data.get("top_k") or 5)
    retrieval_mode = str(node_data.get("retrieval_mode") or "default").strip() or "default"
    kb_ids = [str(kb_id)] if kb_id else ctx.kb_ids

    async with AsyncSessionLocal() as db:
        return await retrieve_hits(
            query,
            tenant_id=UUID(ctx.tenant_id),
            kb_ids=kb_ids,
            db=db,
            top_k=top_k,
            mode=retrieval_mode,
        )


async def _load_prompt_template_content(
    prompt_template_id: str,
    tenant_id: str,
) -> str | None:
    """运行时从模板库加载 content（live 引用，非快照）。"""
    try:
        tid = UUID(str(prompt_template_id))
        tenant_uuid = UUID(tenant_id)
    except (ValueError, TypeError):
        return None

    async with AsyncSessionLocal() as db:
        tpl = await db.get(PromptTemplate, tid)
        if tpl and tpl.tenant_id == tenant_uuid and tpl.is_active and not is_marked_deleted(tpl):
            return tpl.content
    return None


async def _resolve_node_template(
    node_data: dict[str, Any],
    ctx: RunContext,
) -> str:
    """优先 ``prompt_template_id`` 运行时引用，否则内联 ``template``。"""
    prompt_template_id = node_data.get("prompt_template_id")
    if prompt_template_id:
        loaded = await _load_prompt_template_content(str(prompt_template_id), ctx.tenant_id)
        if loaded:
            return loaded
    inline = node_data.get("template")
    if inline:
        return str(inline)
    return _DEFAULT_PROMPT_TEMPLATE


def _apply_prompt_placeholders(
    template: str,
    *,
    query: str,
    hits: Any,
) -> str:
    """将模板占位符 {{用户提问}} / {{检索结果}} 替换为 query 与 hits 上下文。"""
    if isinstance(hits, list) and hits and isinstance(hits[0], dict):
        context = format_hits_context(hits)
    else:
        context = str(hits)
    result = template.replace("{{用户提问}}", query).replace("{{query}}", query)
    return result.replace("{{检索结果}}", context).replace("{{context}}", context)


async def prompt_template(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    """将检索 hits 填入模板，供下游 LLMCall 消费。"""
    template = await _resolve_node_template(node_data, ctx)
    query = str(inputs.get("query") or ctx.inputs.get("query", ""))
    hits = inputs.get("hits") or inputs.get("检索结果") or []
    result = _apply_prompt_placeholders(template, query=query, hits=hits)
    if ctx.system_prompt:
        result = f"{ctx.system_prompt}\n\n{result}"
    return result
