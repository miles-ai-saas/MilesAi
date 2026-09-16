"""MCP 工具的 LLM function name 约定，与按 name 的工具白名单过滤。

纯字符串 / 名称语义，无 DB、无 LangChain 依赖。被 portal 的 MCP 装配与执行分发复用。
"""

from __future__ import annotations

import hashlib
import re

# --- MCP 工具 → LLM function name（OpenAI 仅允许 [A-Za-z0-9_-]，≤64 字符）---

MCP_FUNCTION_PREFIX = "mcp__"
_MAX_FUNCTION_NAME = 64
_INVALID_IDENT_CHARS = re.compile(r"[^A-Za-z0-9_]")


def sanitize_ident(raw: str) -> str:
    """把任意名称清洗为 `[A-Za-z0-9_]`；全非法时返回空串。"""
    return _INVALID_IDENT_CHARS.sub("_", str(raw or "")).strip("_")


def _service_ident(service_name: str) -> str:
    """服务标识：纯 ASCII 名称直接用；含中文等被清洗字符时追加 4 位哈希防塌缩碰撞。"""
    raw = str(service_name or "")
    cleaned = sanitize_ident(raw)
    if cleaned and cleaned == raw:
        return cleaned
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:4]
    return f"{cleaned or 'svc'}_{digest}"


def compose_mcp_tool_name(service_name: str, tool_name: str) -> str:
    """组合 MCP 工具的 function name：``mcp__{service}__{tool}``（超长则截断 + 短哈希）。

    服务名清洗有损（如含中文）时追加 4 位哈希；整体超长时追加 6 位摘要，
    保证同一 (service, tool) 稳定且几乎不碰撞。
    """
    svc = _service_ident(service_name)
    tool = sanitize_ident(tool_name) or "tool"
    name = f"{MCP_FUNCTION_PREFIX}{svc}__{tool}"
    if len(name) <= _MAX_FUNCTION_NAME:
        return name
    digest = hashlib.sha1(f"{service_name}\x00{tool_name}".encode()).hexdigest()[:6]
    # prefix + svc + "__" + tool + "_" + digest ≤ 64
    budget = _MAX_FUNCTION_NAME - len(MCP_FUNCTION_PREFIX) - 2 - 1 - len(digest)
    svc_budget = min(len(svc), max(4, budget // 3))
    tool_budget = max(4, budget - svc_budget)
    return f"{MCP_FUNCTION_PREFIX}{svc[:svc_budget]}__{tool[:tool_budget]}_{digest}"


def is_mcp_tool_name(name: str | None) -> bool:
    """是否为绑定 MCP 服务的 function name。"""
    return bool(name) and str(name).startswith(MCP_FUNCTION_PREFIX)


def select_agent_tools(
    tools: list,
    allowed_slugs: list | None,
    *,
    always_allow: set[str] | None = None,
) -> list:
    """按 ``tool_slugs`` 白名单过滤工具列表。

    MCP 工具经 ``config.mcp_service_ids`` 绑定即视为启用，不受白名单过滤
    （未绑定时工具集合中本就不含 MCP，故不会意外放开）。
    ``always_allow`` 用于强制保留必需工具（如绑定 KB 时的 ``knowledge_search``）。
    """
    if not allowed_slugs:
        return list(tools)
    allowed = {str(s) for s in allowed_slugs} | set(always_allow or ())
    return [t for t in tools if t.name in allowed or is_mcp_tool_name(t.name)]
