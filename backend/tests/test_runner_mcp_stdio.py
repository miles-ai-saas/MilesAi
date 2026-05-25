"""McpStdioClient 组件测试（mock stdin/stdout）。"""

import asyncio
import json
from io import BytesIO

import pytest

from app.runner.mcp_stdio import McpStdioClient


class _FakeStreamWriter:
    def __init__(self) -> None:
        self.buffer = BytesIO()

    def write(self, data: bytes) -> None:
        self.buffer.write(data)

    async def drain(self) -> None:
        pass


class _FakeStreamReader:
    def __init__(self, lines: list[str]) -> None:
        self._lines = [line.encode("utf-8") + b"\n" for line in lines]
        self._idx = 0

    async def readline(self) -> bytes:
        if self._idx >= len(self._lines):
            return b""
        line = self._lines[self._idx]
        self._idx += 1
        return line


@pytest.mark.asyncio
async def test_mcp_stdio_client_request_response():
    writer = _FakeStreamWriter()
    reader = _FakeStreamReader(
        [
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"protocolVersion": "2024-11-05", "capabilities": {}},
                }
            ),
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "echo"}]}}),
        ]
    )
    client = McpStdioClient(writer, reader)
    await client.initialize()
    tools = await client.request("tools/list", {})
    assert tools["tools"][0]["name"] == "echo"
    sent = writer.buffer.getvalue().decode("utf-8").strip().split("\n")
    assert len(sent) >= 3
    init_msg = json.loads(sent[0])
    assert init_msg["method"] == "initialize"
