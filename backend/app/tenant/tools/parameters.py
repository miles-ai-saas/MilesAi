"""工具输入参数 schema 校验与动态 Pydantic 模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, create_model

from app.common.exceptions import BadRequestError

_ALLOWED_TYPES = {"string", "number", "integer", "boolean"}


def normalize_parameters(raw: list | None) -> list[dict]:
    if not raw:
        return []
    names: set[str] = set()
    out: list[dict] = []
    for i, p in enumerate(raw):
        if not isinstance(p, dict):
            raise BadRequestError(f"parameters[{i}] 必须是对象")
        name = str(p.get("name", "")).strip()
        if not name or not name.replace("_", "").isalnum() or not name[0].isalpha():
            raise BadRequestError(f"parameters[{i}].name 无效: {name!r}")
        if name in names:
            raise BadRequestError(f"参数名重复: {name}")
        names.add(name)
        ptype = str(p.get("type", "string"))
        if ptype not in _ALLOWED_TYPES:
            raise BadRequestError(f"parameters[{i}].type 不支持: {ptype}")
        out.append({**p, "name": name, "type": ptype})
    return out


def validate_tool_params(schema: list[dict], params: dict[str, Any]) -> dict[str, Any]:
    schema = normalize_parameters(schema)
    coerced: dict[str, Any] = {}
    for p in schema:
        name = p["name"]
        required = bool(p.get("required"))
        if name in params and params[name] is not None:
            val = params[name]
        elif "default" in p:
            val = p["default"]
        elif required:
            raise BadRequestError(f"缺少必填参数: {name}")
        else:
            continue
        coerced[name] = _coerce(val, p)
    return coerced


def _coerce(val: Any, spec: dict) -> Any:
    t = spec["type"]
    enum = spec.get("enum")
    if t == "string":
        val = str(val)
    elif t == "integer":
        val = int(val)
    elif t == "number":
        val = float(val)
    elif t == "boolean":
        if isinstance(val, str):
            val = val.lower() in ("1", "true", "yes")
        else:
            val = bool(val)
    if enum and val not in enum:
        raise BadRequestError(f"参数 {spec['name']} 必须是 {enum} 之一")
    return val


def parameters_to_pydantic(schema: list[dict]) -> type[BaseModel]:
    schema = normalize_parameters(schema)
    fields: dict[str, Any] = {}
    for p in schema:
        py_type = {"string": str, "integer": int, "number": float, "boolean": bool}[p["type"]]
        default = ... if p.get("required") else p.get("default", None)
        fields[p["name"]] = (py_type, Field(default=default, description=p.get("description")))
    return create_model("ToolParams", **fields)
