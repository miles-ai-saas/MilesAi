"""API 侧 MCP Runner HTTP 客户端。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from app.common.exceptions import BadRequestError
from app.core.config import get_settings
from app.exec.mcp.spec import RunSpec


class RunnerClient:
    """调用独立 mcp-runner 服务；API 进程不 exec 用户命令。"""

    def __init__(self) -> None:
        self._settings = get_settings()

    def _headers(self) -> dict[str, str]:
        token = self._settings.mcp_runner_token
        if not token:
            raise BadRequestError("MCP Runner 未配置 token")
        return {"X-Runner-Token": token, "Content-Type": "application/json"}

    def _base_url(self) -> str:
        return self._settings.mcp_runner_url.rstrip("/")

    async def list_tools(self, spec: RunSpec, connection_config: dict | None) -> list[dict]:
        """经 Runner 拉取 STDIO MCP 工具列表；Runner 报错时抛 ``BadRequestError``。"""
        payload = {
            "run_spec": spec.model_dump(mode="json"),
            "connection_config": connection_config or {},
        }
        data = await self._post("/runner/v1/sessions/mcp/list-tools", payload)
        if not data.get("ok"):
            raise BadRequestError(self._format_error(data))
        return list(data.get("tools") or [])

    async def call_tool(
        self,
        spec: RunSpec,
        tool_name: str,
        arguments: dict,
        connection_config: dict | None,
    ) -> dict:
        """经 Runner 调用 STDIO MCP 工具；输出统一规整为 dict。"""
        payload = {
            "run_spec": spec.model_dump(mode="json"),
            "connection_config": connection_config or {},
            "tool_name": tool_name,
            "arguments": arguments or {},
        }
        data = await self._post("/runner/v1/sessions/mcp/call-tool", payload)
        if not data.get("ok"):
            raise BadRequestError(self._format_error(data))
        output = data.get("output")
        return output if isinstance(output, dict) else {"raw": output}

    async def exec_script(
        self,
        *,
        tenant_id: UUID,
        source: str,
        params: dict,
        tool_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        max_runtime_sec: int = 30,
        max_memory_mb: int = 512,
    ) -> dict:
        """经 Runner 在沙箱执行脚本工具；输出统一规整为 dict。"""
        payload = {
            "tenant_id": str(tenant_id),
            "tool_id": str(tool_id) if tool_id else None,
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "source": source,
            "params": params or {},
            "max_runtime_sec": max_runtime_sec,
            "max_memory_mb": max_memory_mb,
        }
        data = await self._post("/runner/v1/sessions/script/exec", payload)
        if not data.get("ok"):
            raise BadRequestError(self._format_error(data))
        output = data.get("output")
        return output if isinstance(output, dict) else {"result": output}

    async def _post(self, path: str, payload: dict) -> dict[str, Any]:
        spec = payload.get("run_spec") or {}
        timeout = float(spec.get("max_runtime_sec") or payload.get("max_runtime_sec") or 30) + 15
        url = f"{self._base_url()}{path}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload, headers=self._headers())
        except httpx.ConnectError as e:
            raise BadRequestError("无法连接 MCP Runner，请确认服务已启动") from e
        except httpx.TimeoutException as e:
            raise BadRequestError("MCP Runner 请求超时") from e

        if resp.status_code == 401:
            raise BadRequestError("MCP Runner 认证失败")
        if resp.status_code >= 400:
            detail = resp.text[:500] if resp.text else resp.status_code
            raise BadRequestError(f"MCP Runner 错误: {detail}")

        data = resp.json()
        if not isinstance(data, dict):
            raise BadRequestError("MCP Runner 响应格式无效")
        return data

    @staticmethod
    def _format_error(data: dict) -> str:
        code = data.get("error_code") or "RUNNER_ERROR"
        msg = data.get("message") or "Runner 执行失败"
        return f"[{code}] {msg}"
