"""文件解析注册表，按 MIME/扩展名路由到具体解析器。"""

from app.ai.parsers.text_parser import parse_text
from app.common.exceptions import BadRequestError

_TEXT_MIMES = {
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/octet-stream",
}
_TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}


def parse_file(data: bytes, filename: str, mime_type: str) -> str:
    ext = ""
    if "." in filename:
        ext = filename[filename.rfind(".") :].lower()
    if mime_type in _TEXT_MIMES or ext in _TEXT_EXTENSIONS:
        return parse_text(data)
    if mime_type == "application/pdf" or ext == ".pdf":
        return _parse_pdf_stub(data)
    raise BadRequestError(f"暂不支持该文件类型: {mime_type or ext}")


def _parse_pdf_stub(data: bytes) -> str:
    """PDF 完整解析将在后续接入 Docling，此处做占位。"""
    try:
        from pypdf import PdfReader
        from io import BytesIO

        reader = PdfReader(BytesIO(data))
        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        if parts:
            return "\n\n".join(parts)
    except Exception:
        pass
    raise BadRequestError("PDF 解析失败，请稍后重试或上传 TXT/MD")
