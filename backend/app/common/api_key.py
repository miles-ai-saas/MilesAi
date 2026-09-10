"""模型 API Key 格式校验（纯函数，保存与调用前；供运营端与租户域复用）。"""

from __future__ import annotations

import re

from app.common.exceptions import BadRequestError

_SK_PREFIX_VENDORS = frozenset({"qwen", "deepseek", "openai"})

_INVALID_PATTERNS = (
    re.compile(r"^error\s*:", re.I),
    re.compile(r"promise\.reject", re.I),
    re.compile(r"lib/api\.ts", re.I),
    re.compile(r"@[^\s]+:\d+:\d+"),  # JS stack frame
)


def normalize_api_key(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip()
    return key or None


def validate_api_key(key: str, *, vendor: str | None = None) -> str:
    """校验并返回 strip 后的 Key；明显非法时抛 BadRequestError。"""
    normalized = normalize_api_key(key)
    if not normalized:
        raise BadRequestError("API Key 不能为空")

    if len(normalized) < 8:
        raise BadRequestError("API Key 长度过短")

    for pattern in _INVALID_PATTERNS:
        if pattern.search(normalized):
            raise BadRequestError("内容不像有效密钥（疑似错误信息或调试文本）")

    if normalized.isdigit():
        raise BadRequestError("请勿填写纯数字（如手机号、订单号）")

    if vendor in _SK_PREFIX_VENDORS and not normalized.startswith("sk-"):
        raise BadRequestError("该厂商 API Key 通常以 sk- 开头，请从控制台完整复制")

    return normalized


def assert_usable_api_key(key: str, *, model_name: str, vendor: str | None) -> None:
    """调用前二次校验，将脏数据转化为可操作的配置提示。"""
    try:
        validate_api_key(key, vendor=vendor)
    except BadRequestError as exc:
        raise BadRequestError(f"模型「{model_name}」的 API Key 无效：{exc.message}。请在「模型供应商」配置租户密钥，或联系运营在后台更新平台密钥。") from exc
