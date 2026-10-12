"""Celery 侧：从本轮对话抽取/更新长期记忆。"""

from __future__ import annotations

import json
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.models.agent import Agent
from miles_core.soft_delete import is_marked_deleted
from miles_core.tenant import TenantContext
from miles_integrations.langchain.chat_models import ainvoke_chat
from miles_portal.tenant.agents.services.user_memory import MEMORY_KINDS, UserMemoryService, user_memory_enabled
from miles_portal.tenant.models.services.model_resolve import resolve_model_for_invoke
from miles_portal.tenant.models.services.usage import ChatUsageSink

logger = get_logger(__name__)


def parse_memory_json(raw: str) -> dict[str, str]:
    """解析抽取 JSON；仅返回出现的 kind→content（空串表示清除）。"""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for kind in MEMORY_KINDS:
        if kind not in data:
            continue
        val = data.get(kind)
        if val is None:
            out[kind] = ""
        elif isinstance(val, str):
            out[kind] = val.strip()[:4000]
    return out


async def extract_user_memory_async(
    *,
    tenant_id: str,
    user_id: str,
    agent_id: str,
    user_text: str,
    assistant_text: str,
    trace_id: str | None = None,
) -> str:
    """根据本轮快照更新 summary / preference；未启用或无模型则跳过。"""
    tid = UUID(tenant_id)
    uid = UUID(user_id)
    aid = UUID(agent_id)

    async with AsyncSessionLocal() as db:
        agent = (
            await db.execute(
                select(Agent)
                .options(selectinload(Agent.model_config))
                .where(Agent.id == aid, Agent.tenant_id == tid)
            )
        ).scalar_one_or_none()
        if not agent or is_marked_deleted(agent) or not user_memory_enabled(agent):
            return "skipped"
        if not agent.model_config:
            return "no_model"

        ctx = TenantContext(
            user_id=uid,
            tenant_id=tid,
            username="memory-worker",
            is_superuser=True,
            permissions=frozenset(),
        )
        svc = UserMemoryService(db, ctx)
        existing = await svc._list_rows(agent_id=aid, user_id=uid)
        existing_txt = "\n".join(f"{r.kind}: {r.content}" for r in existing) or "（无）"

        prompt = (
            "你是用户记忆整理器。根据本轮对话，更新该用户在此智能体下的长期记忆。\n"
            "只保留稳定、可复用的信息；忽略一次性问题与敏感密钥。\n"
            '输出 JSON：{"summary":"...","preference":"..."}。\n'
            "两个字段都必须出现；无需保留的字段输出空串（表示清除）；有内容则写完整新值（覆盖）。\n"
            f"现有记忆：\n{existing_txt}\n\n"
            f"用户：{(user_text or '')[:2000]}\n助手：{(assistant_text or '')[:2000]}"
        )
        model = await resolve_model_for_invoke(db, agent.model_config, tid)
        usage_sink = ChatUsageSink(tenant_id=tid, model=model, source_id=aid)
        await db.commit()
        raw = await ainvoke_chat(
            model,
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            usage_sink=usage_sink,
        )
        parsed = parse_memory_json(raw)
        for kind, content in parsed.items():
            await svc.upsert(
                tenant_id=tid,
                user_id=uid,
                agent_id=aid,
                kind=kind,
                content=content,
                source_trace_id=trace_id,
            )
        await db.commit()
        logger.info(
            "user_memory_extract done agent=%s user=%s kinds=%s",
            agent_id,
            user_id,
            list(parsed.keys()),
        )
        return "ok"
