import pytest

from miles_common.exceptions import BadRequestError
from miles_exec.mcp.rpc import normalize_tool_call_result
from miles_exec.mcp.tools import normalize_tools
from miles_portal.tenant.mcp.security import validate_mcp_endpoint_url
from miles_portal.tenant.mcp.sse_transport import _assert_same_origin, _json_from_sse_data


def test_normalize_tools_from_list():
    raw = [{"name": "search", "description": "Search places"}]
    assert normalize_tools(raw) == [{"name": "search", "description": "Search places"}]


def test_normalize_tool_call_result_text():
    result = {
        "content": [{"type": "text", "text": "hello"}],
        "isError": False,
    }
    out = normalize_tool_call_result(result)
    assert out["text"] == "hello"
    assert out["isError"] is False


def test_validate_rejects_localhost_when_disabled(monkeypatch):
    monkeypatch.setenv("MCP_ALLOW_PRIVATE_HOSTS", "false")
    from miles_core.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(BadRequestError, match="本机"):
            validate_mcp_endpoint_url("http://127.0.0.1:3001/mcp")
    finally:
        get_settings.cache_clear()


def test_validate_accepts_https():
    assert validate_mcp_endpoint_url("https://mcp.example.com/v1") == "https://mcp.example.com/v1"


def test_sse_same_origin():
    assert _assert_same_origin("http://localhost:3001/sse", "http://localhost:3001/messages") == "http://localhost:3001/messages"


def test_sse_rejects_cross_origin():
    with pytest.raises(BadRequestError, match="不同源"):
        _assert_same_origin("http://localhost:3001/sse", "http://evil.example/messages")


def test_json_from_sse_data():
    msg = _json_from_sse_data('{"jsonrpc":"2.0","id":1,"result":{}}')
    assert msg["id"] == 1
