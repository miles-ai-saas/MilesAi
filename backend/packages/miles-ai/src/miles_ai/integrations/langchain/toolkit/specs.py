"""租户自定义工具 / MCP 工具的中性 spec，以及 JSON Schema → pydantic 的转换。

中性 spec 由 L1 loader 自 ORM 构造；转换器仅生成 LLM 可见的 parameters schema，执行不经它。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, create_model

_INVALID_FIELD_CHARS = re.compile(r"\W")


@dataclass(frozen=True)
class CustomToolSpec:
    """租户自定义工具的 L3 中性描述（L1 loader 自 ORM 构造）。"""

    slug: str
    name: str
    description: str | None
    tool_type: str  # "http" | "script"
    parameters: list[dict]


@dataclass(frozen=True)
class McpToolSpec:
    """绑定 MCP 服务中单个 tool 的 L3 中性描述（L1 loader 自 ``tools_cache`` 构造）。"""

    slug: str  # LLM function name，mcp__{service}__{tool}
    tool_name: str  # MCP tools/call 的原始 name
    service_id: str
    service_name: str
    description: str | None
    input_schema: dict | None  # MCP tools/list 的 inputSchema（JSON Schema）


def _field_name(raw: str) -> str:
    """把 JSON Schema 属性名转为合法 pydantic 字段名（保留可映射的清洗结果）。"""
    name = _INVALID_FIELD_CHARS.sub("_", str(raw or "")).strip("_")
    if not name or name[0].isdigit() or name.startswith("model_"):
        name = f"f_{name}" if name else "f_field"
    return name


def mcp_param_alias(input_schema: dict | None) -> dict[str, str]:
    """返回「pydantic 字段名 → JSON Schema 原始属性名」映射（仅含被清洗的键）。"""
    if not isinstance(input_schema, dict):
        return {}
    props = input_schema.get("properties")
    if not isinstance(props, dict):
        return {}
    return {_field_name(raw): raw for raw in props if _field_name(raw) != raw}


def json_schema_to_pydantic(input_schema: dict | None, *, model_name: str = "McpToolParams") -> type[BaseModel] | None:
    """把 MCP ``inputSchema``（JSON Schema）转为 pydantic 模型，供 LLM function schema 使用。

    支持 string/integer/number/boolean/object/array 与 enum；无可解析属性时返回 ``None``。
    仅用于生成 LLM 可见的 parameters schema，执行不经本模型。
    """
    if not isinstance(input_schema, dict):
        return None
    props = input_schema.get("properties")
    if not isinstance(props, dict) or not props:
        return None
    required = {str(r) for r in (input_schema.get("required") or [])}
    fields: dict[str, Any] = {}
    for raw_name, raw_prop in props.items():
        prop = raw_prop if isinstance(raw_prop, dict) else {}
        py_type = _json_scalar_type(prop.get("type"))
        is_required = raw_name in required
        if is_required:
            annotation: Any = py_type
            default: Any = ...
        else:
            annotation = py_type | None
            default = prop.get("default", None)
        extra: dict[str, Any] = {}
        enum = prop.get("enum")
        if isinstance(enum, list) and enum:
            extra["enum"] = enum
        fields[_field_name(raw_name)] = (
            annotation,
            Field(default=default, description=prop.get("description"), json_schema_extra=extra or None),
        )
    return create_model(model_name, **fields)


def _json_scalar_type(json_type: Any) -> Any:
    """JSON Schema type → python 类型；联合类型取首个非 null。"""
    if isinstance(json_type, list):
        json_type = next((t for t in json_type if t != "null"), None)
    return {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "object": dict,
        "array": list,
    }.get(json_type, Any)
