"""服务端对话记忆：从 PG 会话加载近期 user/assistant，按字符预算截断后供 LLM 注入。

直连 / tool_agent 以 messages 列表注入；RAG / Flow / A2A 宿主以文本块拼进 system_prompt。
检索 query 仍用本轮问题，避免历史污染向量检索。

跨会话长期记忆见 ``user_memory.py``（``agt_user_agent_memories``），与短程并列注入
直连 / tool / RAG / Flow / A2A 宿主（subagent 编排路径仍仅短程）。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.config import get_settings
from miles_core.models.agent.chat_session import AgentChatMessage, AgentChatSession

_HISTORY_ROLES = frozenset({"user", "assistant"})


def format_history_block(messages: list[dict[str, Any]]) -> str:
    """将历史格式化为可拼进 system_prompt 的文本块；空列表返回空串。"""
    if not messages:
        return ""
    lines: list[str] = []
    for msg in messages:
        role = str(msg.get("role") or "")
        content = str(msg.get("content") or "").strip()
        if not content or role not in _HISTORY_ROLES:
            continue
        label = "用户" if role == "user" else "助手"
        lines.append(f"{label}：{content}")
    if not lines:
        return ""
    return "\n\n【近期对话】\n" + "\n".join(lines)


def truncate_messages_by_chars(
    messages: list[dict[str, Any]],
    *,
    max_chars: int,
) -> list[dict[str, Any]]:
    """从尾部保留消息，使 content 字符合计不超过 ``max_chars``；单条超长则截断正文尾部。"""
    if max_chars <= 0 or not messages:
        return []

    kept: list[dict[str, Any]] = []
    used = 0
    for msg in reversed(messages):
        content = str(msg.get("content") or "")
        if not content:
            continue
        role = str(msg.get("role") or "")
        if role not in _HISTORY_ROLES:
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(content) > remaining:
            # 保留尾部，贴近「最近上下文」
            content = content[-remaining:]
            kept.append({"role": role, "content": content})
            break
        kept.append({"role": role, "content": content})
        used += len(content)
    kept.reverse()
    return kept


async def load_chat_history_messages(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    conversation_id: str | None,
    max_chars: int | None = None,
    max_messages: int | None = None,
) -> list[dict[str, str]]:
    """按 conversation_id 加载近期历史；会话不存在或不匹配租户/智能体时返回空列表。"""
    cid = (conversation_id or "").strip()
    if not cid:
        return []

    settings = get_settings()
    budget = max_chars if max_chars is not None else int(settings.agent_chat_history_max_chars)
    limit = max_messages if max_messages is not None else int(settings.agent_chat_history_max_messages)
    if budget <= 0 or limit <= 0:
        return []

    session = await db.get(AgentChatSession, cid)
    if not session or session.agent_id != agent_id or session.tenant_id != tenant_id:
        return []

    stmt = (
        select(AgentChatMessage.role, AgentChatMessage.content)
        .where(
            AgentChatMessage.session_id == cid,
            AgentChatMessage.role.in_(_HISTORY_ROLES),
        )
        .order_by(AgentChatMessage.sort_index.desc())
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).all())
    rows.reverse()
    raw = [{"role": str(role), "content": str(content or "")} for role, content in rows]
    return truncate_messages_by_chars(raw, max_chars=budget)
