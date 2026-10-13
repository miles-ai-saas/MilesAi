"""JSON-RPC / Task 响应文本解析。"""

from __future__ import annotations

from typing import Any

_RESULT_TEXT_KEYS = ("text", "answer", "content", "message")
_MESSAGE_TEXT_KEYS = ("text", "content", "parts")


def _first_part_text(value: Any) -> str | None:
    """``parts`` 形态（``[{"text": ...}]``）取首项文本；非该形态返回 None。"""
    if not isinstance(value, list) or not value:
        return None
    first = value[0]
    if isinstance(first, dict) and first.get("text"):
        return str(first["text"]).strip()
    return None


def _text_from_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """按 ``keys`` 顺序取首个非空字符串（全空白视为未命中）。"""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _text_or_parts_from_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """按 ``keys`` 顺序取非空字符串；该项为 ``parts`` 形态时取首项文本。"""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        parts_text = _first_part_text(value)
        if parts_text:
            return parts_text
    return None


def _text_from_result_payload(result: dict[str, Any]) -> str | None:
    """``result`` 字典 → 可读文本：常见文本键 → ``message`` 下钻 → ``artifacts`` 下钻。"""
    text = _text_from_keys(result, _RESULT_TEXT_KEYS)
    if text:
        return text
    message = result.get("message")
    if isinstance(message, dict):
        text = _text_or_parts_from_keys(message, _MESSAGE_TEXT_KEYS)
        if text:
            return text
    artifacts = result.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        artifact = artifacts[0]
        if isinstance(artifact, dict):
            text = _first_part_text(artifact.get("parts"))
            if text:
                return text
    return None


def _jsonrpc_error(data: object) -> tuple[object, str] | None:
    """顶层 ``error`` → ``(code, message)``；无 ``error`` 返回 ``None``。

    JSON-RPC 里 ``error`` 与 ``result`` 互斥，故本函数是「本次调用成功还是失败」的判据。
    此前这个判断被交给 ``_extract_text_from_response``（它刻意让 error 优先于 result 并
    把消息榨成文本，见其特征化测试），结果是协议级失败被当成对端的「回答」写进主模型素材。
    """
    if not isinstance(data, dict) or "error" not in data:
        return None
    err = data["error"]
    if isinstance(err, dict):
        return err.get("code"), str(err.get("message") or err)
    return None, str(err)


def _extract_text_from_response(data: Any) -> str:
    """从 JSON-RPC / HTTP 响应中提取可读文本。"""
    if isinstance(data, str):
        return data.strip()
    if not isinstance(data, dict):
        return str(data)
    if "error" in data:
        err = data["error"]
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err)
    result = data.get("result", data)
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        text = _text_from_result_payload(result)
        if text:
            return text
    return str(result)[:4000]
