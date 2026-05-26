"""MCP STDIO JSON-RPC 客户端（newline-delimited JSON）。"""

from __future__ import annotations

import json
from typing import Any

from app.common.exceptions import BadRequestError
from app.tenant.mcp.constants import MCP_PROTOCOL_VERSION
from app.tenant.mcp.rpc import parse_jsonrpc_result


class McpStdioClient:
    """对子进程 stdin/stdout 读写 MCP JSON-RPC 消息。"""

    def __init__(self, stdin, stdout) -> None:
        self._stdin = stdin
        self._stdout = stdout
        self._next_id = 1

    async def initialize(self) -> dict:
        result = await self.request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "milesai-runner", "version": "1.0.0"},
            },
        )
        await self.notify("notifications/initialized", {})
        return result if isinstance(result, dict) else {}

    async def notify(self, method: str, params: dict | None = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        await self._write(msg)

    async def request(self, method: str, params: dict | None = None) -> Any:
        req_id = self._next_id
        self._next_id += 1
        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }
        await self._write(msg)
        return await self._read_response(req_id)

    async def _write(self, msg: dict) -> None:
        line = json.dumps(msg, ensure_ascii=False) + "\n"
        self._stdin.write(line.encode("utf-8"))
        await self._stdin.drain()

    async def _read_response(self, req_id: int) -> Any:
        while True:
            line = await self._stdout.readline()
            if not line:
                raise BadRequestError("MCP 进程 stdout 已关闭")
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise BadRequestError(f"MCP 响应非 JSON: {text[:200]}") from e
            if not isinstance(data, dict):
                continue
            if "method" in data and "id" not in data:
                continue
            if data.get("id") != req_id:
                continue
            return parse_jsonrpc_result(data)
