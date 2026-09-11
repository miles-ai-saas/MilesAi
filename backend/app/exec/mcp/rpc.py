"""
MCP JSON-RPC 解析与 ``tools/call`` 结果规范化。

``parse_jsonrpc_result``：统一处理 ``error`` / ``result`` 信封。
``normalize_tool_call_result``：将 MCP ``content[]`` 块聚合为 API ``output.text``。
"""

from __future__ import annotations

from typing import Any

from app.common.exceptions import BadRequestError


def parse_jsonrpc_result(data: dict) -> Any:
    """
    从完整 JSON-RPC 信封中提取 result，或将 error 转为 BadRequestError。

    调用方（client / sse_transport）只关心业务 result，不处理 jsonrpc 版本字段。
    """
    if not isinstance(data, dict):
        raise BadRequestError("MCP 响应格式无效")
    if "error" in data and data["error"] is not None:
        err = data["error"]
        if isinstance(err, dict):
            message = err.get("message") or err.get("data") or str(err)
            code = err.get("code")
            suffix = f" (code={code})" if code is not None else ""
            raise BadRequestError(f"MCP 远程错误: {message}{suffix}")
        raise BadRequestError(f"MCP 远程错误: {err}")
    if "result" not in data:
        raise BadRequestError("MCP 响应缺少 result 字段")
    return data["result"]


def normalize_tool_call_result(result: Any) -> dict:
    """
    将 tools/call 的 result 规范为租户 API 的 output 字段。

    MCP 规范中 result 常含 content[]（type=text 等）；此处聚合为 text 便于前端展示。
    """
    if not isinstance(result, dict):
        return {"raw": result, "text": str(result) if result is not None else None}

    content = result.get("content")
    texts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    texts.append(str(block.get("text", "")))
                else:
                    # 非 text 块仍尝试取 text 字段或整段序列化
                    texts.append(str(block.get("text") or block))
            elif block is not None:
                texts.append(str(block))

    return {
        "content": content,
        "text": "\n".join(t for t in texts if t) or None,
        "isError": bool(result.get("isError")),
        "structuredContent": result.get("structuredContent"),
    }
