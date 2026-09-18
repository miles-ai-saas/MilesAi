"""数据脱敏工具：PII（个人敏感信息）掩码处理。

支持的脱敏类型：
- 手机号：保留前 3 后 2 → 138******12
- 邮箱：保留前 2 → ab***@domain.com
- 身份证：保留前 3 后 4 → 310****1234
- 银行卡：保留前 4 后 4 → 6222****8888
- IP 地址：全掩 → *.*.*.*

**当前状态：无调用方（未接线）** —— 自引入起全仓无任何 ``import``，故对话/流程输出
**实际并未**做过这层脱敏；产品文档对应条目已标注「未接线」。接入前需先定调用路径
（输出前？写日志前？）与误伤边界（如正文里的合法数字串）。
"""

import re

_PATTERNS: list[tuple[str, str, str]] = [
    # (名称, 正则, 替换模板)
    ("手机号", r"(?<!\d)1[3-9]\d{9}(?!\d)", r"1**********{tail}"),
    ("邮箱", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", r"***@{domain}"),
    ("身份证", r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)", r"{prefix}****{suffix}"),
    ("银行卡", r"(?<!\d)\d{16,19}(?!\d)", r"{prefix}****{suffix}"),
    ("IP 地址", r"\b(?:\d{1,3}\.){3}\d{1,3}\b", r"*.*.*.*"),
]

_PHONE_TAIL = re.compile(r"1[3-9]\d{9}")
_EMAIL_PARTS = re.compile(r"([a-zA-Z0-9._%+-]+)@(.+)")
_ID_TAIL = re.compile(r"[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]")
_CARD_TAIL_PAT = re.compile(r"(\d{1,6})(\d+)(.{4})$")


def _mask_phone(match: re.Match) -> str:
    """手机号掩码：保留末 2 位。"""
    val = match.group(0)
    tail = val[-2:]
    return f"1**********{tail}"


def _mask_email(match: re.Match) -> str:
    """邮箱掩码：保留用户名前 2 字符与域名。"""
    val = match.group(0)
    parts = val.split("@", 1)
    if len(parts) == 2:
        return f"{parts[0][:2]}***@{parts[1]}"
    return "***@***"


def _mask_id_card(match: re.Match) -> str:
    """身份证掩码：保留前 3 后 4 位。"""
    val = match.group(0)
    prefix = val[:3]
    suffix = val[-4:]
    return f"{prefix}****{suffix}"


def _mask_bank_card(match: re.Match) -> str:
    """银行卡掩码：保留前 4 后 4 位。"""
    val = match.group(0)
    prefix = val[:4]
    suffix = val[-4:]
    return f"{prefix}****{suffix}"


def _mask_ip(match: re.Match) -> str:
    """IP 地址全掩。"""
    return "*.*.*.*"


_MASKERS = {
    "手机号": _mask_phone,
    "邮箱": _mask_email,
    "身份证": _mask_id_card,
    "银行卡": _mask_bank_card,
    "IP 地址": _mask_ip,
}


def desensitize(text: str) -> str:
    """对常见 PII 字段进行掩码处理，返回脱敏后文本。"""
    if not text:
        return text
    result = text
    for name, pattern, _ in _PATTERNS:
        masker = _MASKERS.get(name)
        if masker:
            result = re.sub(pattern, masker, result)
    return result
