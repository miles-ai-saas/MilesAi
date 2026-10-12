"""A2A 入站 ``message.parts`` 纯解析（无 ORM / 无 DB）。

支持 ``text`` / ``file``（``bytes`` 或 ``data:`` URI）/ ``data``；远程 ``http(s)`` URI
故意不拉取，避免 SSRF。``kind`` 与历史 ``type`` 判别字段均接受。
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass, field

from miles_ai.rag.parse.media import is_image_file
from miles_ai.rag.parse.upload_policy import is_kb_upload_allowed, kb_upload_allowed_hint
from miles_common.exceptions import BadRequestError

#: 与识图链路 ``MAX_MEDIA_PER_TURN`` 对齐的入站文件数上限。
MAX_INBOUND_FILES = 10
#: 单文件解码后上限（与 ``MAX_IMAGE_BYTES`` 同量级）。
MAX_INBOUND_FILE_BYTES = 10 * 1024 * 1024
#: ``data`` part 序列化进 query 的字符上限，防撑爆对话入口。
MAX_DATA_PART_CHARS = 8000

_DATA_URL_RE = re.compile(
    r"^data:(?P<mime>[^;,]*)?(?:;charset=[^;,]+)?(?:;base64)?,(?P<data>.*)$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class InboundFileBytes:
    """已解码的入站文件字节（尚未落库）。"""

    filename: str
    mime_type: str
    content: bytes


@dataclass
class ParsedInboundParts:
    """``message.parts`` 解析结果。"""

    texts: list[str] = field(default_factory=list)
    files: list[InboundFileBytes] = field(default_factory=list)
    data_texts: list[str] = field(default_factory=list)

    @property
    def has_content(self) -> bool:
        return bool(self.texts or self.files or self.data_texts)


def _part_kind(part: dict) -> str | None:
    """取 part 判别：规范 ``kind``，兼容文档里误写的 ``type``，再按字段推断。"""
    raw = part.get("kind") if part.get("kind") is not None else part.get("type")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    if isinstance(part.get("text"), str):
        return "text"
    if isinstance(part.get("file"), dict):
        return "file"
    if "data" in part:
        return "data"
    return None


def _decode_base64_payload(raw: str, *, where: str) -> bytes:
    """解码 base64；非法编码或超限抛 ``BadRequestError``。"""
    payload = raw.strip()
    if not payload:
        raise BadRequestError(f"{where} 为空")
    # 粗估：base64 膨胀约 4/3；超限直接拒，避免解出巨型缓冲。
    if len(payload) > (MAX_INBOUND_FILE_BYTES * 4) // 3 + 64:
        raise BadRequestError(f"{where} 过大（上限 {MAX_INBOUND_FILE_BYTES // (1024 * 1024)}MB）")
    try:
        data = base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise BadRequestError(f"{where} 不是合法的 base64") from exc
    if len(data) > MAX_INBOUND_FILE_BYTES:
        raise BadRequestError(f"{where} 过大（上限 {MAX_INBOUND_FILE_BYTES // (1024 * 1024)}MB）")
    if not data:
        raise BadRequestError(f"{where} 解码后为空")
    return data


def _decode_data_uri(uri: str) -> tuple[bytes, str | None]:
    """解析 ``data:[mime][;base64],payload``；非 data: 由调用方拦截。"""
    match = _DATA_URL_RE.match(uri.strip())
    if not match:
        raise BadRequestError("file.uri data URL 格式非法")
    mime = (match.group("mime") or "").strip() or None
    payload = match.group("data") or ""
    # data URL 规范：有 ;base64 才按 base64；无标记时按百分号解码。主流 A2A 客户端
    # 几乎都带 base64，这里对「像 base64 的 payload」也尝试 base64，失败再原文。
    if ";base64" in uri.split(",", 1)[0].lower():
        return _decode_base64_payload(payload, where="file.uri data URL"), mime
    try:
        return _decode_base64_payload(payload, where="file.uri data URL"), mime
    except BadRequestError:
        raw = payload.encode("utf-8")
        if len(raw) > MAX_INBOUND_FILE_BYTES:
            raise BadRequestError(f"file.uri 过大（上限 {MAX_INBOUND_FILE_BYTES // (1024 * 1024)}MB）") from None
        if not raw:
            raise BadRequestError("file.uri data URL 为空") from None
        return raw, mime


def _parse_file_part(part: dict, *, index: int) -> InboundFileBytes:
    """``kind=file`` → 内存字节；仅 ``bytes`` 或 ``data:`` URI。"""
    file_obj = part.get("file")
    if not isinstance(file_obj, dict):
        raise BadRequestError(f"parts[{index}].file 必须是对象")

    name_raw = file_obj.get("name")
    filename = name_raw.strip() if isinstance(name_raw, str) and name_raw.strip() else f"a2a-part-{index}"
    mime_raw = file_obj.get("mimeType")
    if not isinstance(mime_raw, str) or not mime_raw.strip():
        mime_raw = file_obj.get("mime_type")
    mime_type = mime_raw.strip() if isinstance(mime_raw, str) and mime_raw.strip() else "application/octet-stream"

    raw_bytes = file_obj.get("bytes")
    uri = file_obj.get("uri")
    if isinstance(raw_bytes, str) and raw_bytes.strip():
        content = _decode_base64_payload(raw_bytes, where=f"parts[{index}].file.bytes")
    elif isinstance(uri, str) and uri.strip():
        if not uri.strip().lower().startswith("data:"):
            raise BadRequestError(
                f"parts[{index}].file.uri 仅支持 data: URL；远程 http(s) 暂不拉取（防 SSRF）"
            )
        content, uri_mime = _decode_data_uri(uri)
        if uri_mime:
            mime_type = uri_mime
    else:
        raise BadRequestError(f"parts[{index}].file 须提供 bytes 或 data: uri")

    if not is_kb_upload_allowed(filename, mime_type):
        raise BadRequestError(f"不支持的文件类型: {mime_type}。{kb_upload_allowed_hint()}")

    return InboundFileBytes(filename=filename, mime_type=mime_type, content=content)


def _serialize_data_part(data: object, *, index: int) -> str:
    """``kind=data`` → 可拼进 query 的文本（截断）。"""
    if isinstance(data, str):
        text = data.strip()
    else:
        try:
            text = json.dumps(data, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as exc:
            raise BadRequestError(f"parts[{index}].data 无法序列化") from exc
    if not text:
        raise BadRequestError(f"parts[{index}].data 为空")
    if len(text) > MAX_DATA_PART_CHARS:
        text = text[: MAX_DATA_PART_CHARS - 1] + "…"
    return text


def parse_inbound_parts(params: dict) -> ParsedInboundParts:
    """解析 A2A ``params.message.parts``；无任何可用内容抛 ``BadRequestError``。"""
    message = params.get("message")
    if not isinstance(message, dict):
        raise BadRequestError("message/send 缺少 message 参数")
    parts = message.get("parts")
    if not isinstance(parts, list):
        raise BadRequestError("message/send 的 message.parts 必须是数组")

    parsed = ParsedInboundParts()
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            continue
        kind = _part_kind(part)
        if kind == "text":
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                parsed.texts.append(text.strip())
        elif kind == "file":
            if len(parsed.files) >= MAX_INBOUND_FILES:
                raise BadRequestError(f"file parts 过多（上限 {MAX_INBOUND_FILES}）")
            parsed.files.append(_parse_file_part(part, index=index))
        elif kind == "data":
            if "data" not in part:
                raise BadRequestError(f"parts[{index}] data 缺少 data 字段")
            parsed.data_texts.append(_serialize_data_part(part.get("data"), index=index))
        # 未知 kind：忽略（与旧 extract 对非 text 静默跳过一致），避免偶发扩展字段整请求失败。

    if not parsed.has_content:
        raise BadRequestError("message/send 的 parts 中没有可用的 text/file/data 内容")
    return parsed


def compose_inbound_query(
    parsed: ParsedInboundParts,
    *,
    non_image_notes: list[str] | None = None,
) -> str:
    """拼对话 ``query``：文本 + 结构化 data + 非图片附件说明。"""
    chunks: list[str] = list(parsed.texts)
    for snippet in parsed.data_texts:
        chunks.append(f"[结构化数据]\n{snippet}")
    if non_image_notes:
        chunks.extend(non_image_notes)
    return "\n".join(chunks)


def is_inbound_image(file: InboundFileBytes) -> bool:
    """是否进入 ``ChatRequest.media`` 识图链路。"""
    return is_image_file(file.filename, file.mime_type)
