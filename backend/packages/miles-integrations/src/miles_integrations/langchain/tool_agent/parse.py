"""伪 tool_call 文本检测与参数提取（供 tool_agent 循环兜底）。"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

# 生图/生视频参数特征字段，用于判断 LLM 是否把参数 JSON 输出到正文了
_GENERATIVE_PARAM_KEYS = frozenset(
    {
        "prompt",
        "size",
        "n",
        "duration",
        "resolution",
        "image_attachment_id",
        "model_config_id",
    }
)

# LLM 输出中表示"我想生图但没有正确调用 tool"的意图短语
_GENERATIVE_INTENT_PHRASES = frozenset(
    {
        "正在为您生成",
        "正在生成图片",
        "正在生成图像",
        "开始生图",
        "开始生成",
        "为您生成图片",
        "正在创作",
        "正在绘制",
        "图片生成中",
        "图像生成中",
    }
)

# 从文本中提取 JSON 对象的模式（匹配最外层 { ... }，支持嵌套）
_JSON_OBJECT_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)

# 合法 UUID 格式
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# 需要校验 UUID 格式的参数名
_UUID_PARAM_NAMES = frozenset({"model_config_id", "image_attachment_id", "last_frame_attachment_id"})


def _clean_uuid_params(params: dict) -> dict:
    """剔除参数中非 UUID 格式的值（如 "taobao-product"、"ref1" 等占位符），
    避免下游 UUID() 构造崩溃。"""
    cleaned = dict(params)
    for key in _UUID_PARAM_NAMES:
        val = cleaned.get(key)
        if isinstance(val, str) and not _UUID_RE.match(val):
            del cleaned[key]
    return cleaned


def _looks_like_tool_call_simulation(content: Any, tool_names: list[str]) -> bool:
    """检测 LLM 响应内容是否在文字中模拟了工具调用（而非真正发起 tool_call）。

    覆盖以下盲区：
    - 裸 JSON 如 ``{"prompt": "...", "size": "1024x1024"}``（无工具名、无中文提示）
    - 函数式写法 ``generate_image({"prompt": "..."})``（缺少 "function" 关键词）
    - OpenAI function call 格式 ``{"function": "generate_image", "arguments": {..."prompt":..."}}``——参数嵌套在 arguments 内
    - 代码块内的 JSON 参数（无中文提示词）
    - 文本中混杂的 JSON 参数（如 "好的，参数如下：{"prompt": "xxx"}"）
    """
    if not isinstance(content, str) or not content:
        return False
    content_stripped = content.strip()
    tool_mentioned = any(name in content_stripped for name in tool_names)

    # 情况 A: 输出中提到了工具名
    if tool_mentioned:
        # A1: 带代码块的 JSON
        if re.search(r"```(?:json)?\s*\{", content_stripped, re.DOTALL):
            return True
        # A2: 类似 "generate_image({\"prompt\": ...})" 的直接调用写法
        tool_call_like = any(re.search(rf"{re.escape(name)}\s*\(", content_stripped) for name in tool_names)
        if tool_call_like:
            return True
        # A3: 输出含 "function"+"arguments"/"params" 键——典型的 function call JSON
        #     无论是否有中文提示，都应拦截
        has_function_args = '"function"' in content_stripped and ('"arguments"' in content_stripped or '"params"' in content_stripped)
        if has_function_args:
            return True

    # 情况 B: 输出中包含长得像生图/生视频参数的 JSON 对象
    json_candidates = _JSON_OBJECT_PATTERN.findall(content_stripped)
    for candidate in json_candidates:
        try:
            parsed = json.loads(candidate)
            if not isinstance(parsed, dict):
                continue
            # B1: 顶层就有生图参数（如裸 {"prompt": "...", "size": "1024x1024"}）
            if any(k in parsed for k in _GENERATIVE_PARAM_KEYS):
                return True
            # B2: 参数嵌套在 "arguments" 内（如 {"function": "generate_image", "arguments": {...}}）
            inner_args = parsed.get("arguments")
            if isinstance(inner_args, dict) and any(k in inner_args for k in _GENERATIVE_PARAM_KEYS):
                return True
        except (json.JSONDecodeError, TypeError):
            # 静默可接受：本判据只是启发式之一，JSON 不合法即「不像工具调用模拟」，继续走其它判据。
            pass

    # 情况 C: 输出中包含"生成意图"短语（如"正在为您生成图片…"），但没有 JSON 参数
    #           说明 LLM 有意生图但不会用 tool_calls，需要兜底处理
    if any(phrase in content_stripped for phrase in _GENERATIVE_INTENT_PHRASES):
        return True

    return False


# ---------------------------------------------------------------------------
# Python kwargs 解析：用 ast 替代正则，天然覆盖所有 Python 字面量语法
# ---------------------------------------------------------------------------


def _parse_as_python_kwargs(params_text: str) -> dict[str, Any] | None:
    """通过构造 ``_dummy(key=..., ...)`` 并用 ``ast`` 解析，
    可靠提取 Python 风格关键字参数，无需手写正则。"""
    source = f"_dummy({params_text})"
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # 静默可接受：不是合法的 Python 关键字参数形式；返回 None 交给下一种解析器。
        return None
    if not tree.body:
        return None
    call = tree.body[0].value
    if not isinstance(call, ast.Call):
        return None
    result: dict[str, Any] = {}
    for kw in call.keywords:
        try:
            result[kw.arg] = ast.literal_eval(kw.value)
        except (ValueError, TypeError):
            result[kw.arg] = ast.unparse(kw.value)
    return result if result else None


def _get_schema_for(tools_by_name: dict[str, Any], tool_name: str) -> type | None:
    """从工具名查找 Pydantic args_schema 类。"""
    tool = tools_by_name.get(tool_name)
    if tool is None or not hasattr(tool, "args_schema"):
        return None
    schema = tool.args_schema
    return type(schema) if schema is not None else None


def _validate_and_clean(
    params: dict[str, Any],
    tools_by_name: dict[str, Any],
    tool_name: str,
) -> dict[str, Any]:
    """清理 UUID + 用工具 schema 校验/转换，schema 失败时保留原始提取结果。"""
    cleaned = _clean_uuid_params(params)
    schema_cls = _get_schema_for(tools_by_name, tool_name)
    if schema_cls is None:
        return cleaned
    try:
        return schema_cls(**cleaned).model_dump(exclude_unset=False)
    except Exception:
        return cleaned


# ---------------------------------------------------------------------------
# 从 LLM 文本输出中提取工具调用信息
# ---------------------------------------------------------------------------


def _extract_tool_params_from_text(
    content: str,
    tools_by_name: dict[str, Any],
) -> tuple[str, dict] | None:
    """从 LLM 文本中提取工具名 + 参数，支持以下格式：

    - ``generate_image(prompt="...", size="...", n=1)``    ← Python kwargs（ast 解析 → schema 校验）
    - ``generate_image({"prompt": ..., "size": ...})``     ← JSON 内嵌 → schema 校验
    - ``{"tool": "generate_image", ...}``                  ← tool-keyed JSON
    - ``{"function": "generate_image", "arguments": {...}}`` ← OpenAI-style
    - 裸 ``{"prompt": "...", "size": "1024x1024"}``       ← 按参数特征推断工具名
    """
    tool_names = list(tools_by_name.keys())
    clean = re.sub(r"```(?:json|python)?\s*", "", content).strip("` \n\r\t")

    # 1) tool_name( ... ) —— 平衡括号匹配 → JSON / ast kwargs
    for name in sorted(set(tool_names), key=len, reverse=True):
        m = re.search(rf"\b{re.escape(name)}\s*\(", clean)
        if not m:
            continue
        body_start = m.end()
        depth, body_end = 1, body_start
        for i, ch in enumerate(clean[body_start:], body_start):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    body_end = i
                    break
        body = clean[body_start:body_end].strip()
        # JSON 优先
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return name, _validate_and_clean(parsed, tools_by_name, name)
        except (json.JSONDecodeError, TypeError):
            # 静默可接受：形似工具调用的文本里 JSON 不合法；交给后续 kwargs / 正则解析。
            pass
        # 回退 ast kwargs
        kwargs = _parse_as_python_kwargs(body)
        if kwargs:
            return name, _validate_and_clean(kwargs, tools_by_name, name)

    # 2) 独立 JSON 对象（无工具名前缀）
    for candidate in _JSON_OBJECT_PATTERN.findall(clean):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            # 静默可接受：候选 JSON 片段不合法即试下一个；全部候选都失败才落到正则解析。
            continue
        if not isinstance(parsed, dict):
            continue

        # {"tool": "generate_image", ...}
        tool_key = parsed.get("tool")
        if isinstance(tool_key, str) and tool_key in tools_by_name:
            params = {k: v for k, v in parsed.items() if k != "tool"}
            return tool_key, _validate_and_clean(params, tools_by_name, tool_key)

        # {"function": "generate_image", "arguments": {...}}
        func = parsed.get("function")
        if isinstance(func, str) and func in tools_by_name:
            inner = parsed.get("arguments")
            params = inner if isinstance(inner, dict) else {k: v for k, v in parsed.items() if k != "function"}
            return func, _validate_and_clean(params, tools_by_name, func)

        # 裸参数 → 按特征推断工具名（只认真正的生图/生视频工具，不猜）
        if any(k in parsed for k in _GENERATIVE_PARAM_KEYS):
            has_video = "duration" in parsed or "resolution" in parsed
            for n in tool_names:
                if has_video and "video" in n:
                    return n, _validate_and_clean(parsed, tools_by_name, n)
                if not has_video and "image" in n and "video" not in n:
                    return n, _validate_and_clean(parsed, tools_by_name, n)
            # 没有对应的生成工具就不认领这个 JSON，继续看下一个候选。
            # 曾兜底 ``return tool_names[0]``：会把生图参数塞给 calculator 之类的工具，
            # 白跑一次失败重试；tools 为空时还会 IndexError。
            continue

    return None
