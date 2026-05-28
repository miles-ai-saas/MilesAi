"""MCP 种子脚本（不直接 import ORM，避免与 app.models 循环依赖）。"""

from scripts.seed.mcp import SEED_MCP_SERVICES


def _status_value(raw: object) -> str:
    return getattr(raw, "value", raw) if raw is not None else ""


def test_seed_mcp_scenarios_coverage():
    assert len(SEED_MCP_SERVICES) == 8
    transports = {s["transport"] for s in SEED_MCP_SERVICES}
    assert transports == {"http", "sse", "stdio"}
    statuses = {_status_value(s["status"]) for s in SEED_MCP_SERVICES}
    assert statuses >= {"active", "inactive", "error"}

    scenarios = {s["connection_config"]["seed_scenario"] for s in SEED_MCP_SERVICES}
    assert "http_streamable" in scenarios
    assert "stdio_filesystem" in scenarios
    assert "sync_error" in scenarios

    active_with_tools = [s for s in SEED_MCP_SERVICES if _status_value(s["status"]) == "active" and s["tools_cache"]]
    assert len(active_with_tools) >= 3
