"""
PDF / Office / 部分图片：Docling → LangChain Document（Markdown 导出）。

依赖 ``docling``（随 miles-ai 声明）；``PARSE_PDF_BACKEND=docling`` 时 PDF 也走此路径。
分页通过 ``PAGE_BREAK_PLACEHOLDER`` 插入标记，供后续拆分 page_no。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from langchain_core.documents import Document

from miles_core.logging import get_logger

logger = get_logger(__name__)

# 导出 Markdown 时插入的分页标记（用于拆分 page_no）
PAGE_BREAK_PLACEHOLDER = "\n\n<!-- MILESAI_PAGE_BREAK -->\n\n"

# Docling 常见可转换扩展名（与 DocumentConverter 默认允许格式对齐）。
# 这是**解析能力**声明，不等于上传白名单：TIFF/BMP 可解析但白名单刻意不收
# （``parse_image`` 不认，收了会「可上传却必解析失败」）；图片类扩展名在此仅声明
# 底层能力，入库实际由 ``loaders`` 的 ``is_image_file`` 分支先拦截。
DOCLING_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".html",
        ".htm",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".bmp",
    }
)

_SUFFIX_BY_EXT = {
    ".pdf": ".pdf",
    ".docx": ".docx",
    ".pptx": ".pptx",
    ".xlsx": ".xlsx",
    ".html": ".html",
    ".htm": ".htm",
    ".png": ".png",
    ".jpg": ".jpg",
    ".jpeg": ".jpeg",
    ".tif": ".tif",
    ".tiff": ".tiff",
    ".bmp": ".bmp",
}


def markdown_pages_to_documents(
    markdown: str,
    *,
    filename: str,
    dl_doc: object | None = None,
) -> list[Document]:
    """将 Markdown（含分页占位符或多页导出）转为带 page metadata 的 Document 列表。"""
    text = (markdown or "").strip()
    if not text:
        return []

    # 优先：整篇 export 时带分页占位符（metadata.page 为 0-based）
    if PAGE_BREAK_PLACEHOLDER in text:
        parts = [p.strip() for p in text.split(PAGE_BREAK_PLACEHOLDER) if p.strip()]
        if len(parts) > 1:
            return [
                Document(
                    page_content=part,
                    metadata={"source": filename, "parser": "docling", "page": idx},
                )
                for idx, part in enumerate(parts)
            ]

    # 次选：按页 export（大 PDF 上 page_no 参数可能有 docling 已知问题，故占位符优先）
    pages = getattr(dl_doc, "pages", None) if dl_doc is not None else None
    page_count = len(pages) if pages else 0
    if page_count > 1 and hasattr(dl_doc, "export_to_markdown"):
        docs: list[Document] = []
        for page_one_based in range(1, page_count + 1):
            try:
                page_md = dl_doc.export_to_markdown(page_no=page_one_based)  # type: ignore[union-attr]
            except Exception as exc:
                logger.warning(
                    "Docling 按页导出失败 page=%s: %s",
                    page_one_based,
                    exc,
                )
                break
            page_text = (page_md or "").strip()
            if page_text:
                docs.append(
                    Document(
                        page_content=page_text,
                        metadata={
                            "source": filename,
                            "parser": "docling",
                            "page": page_one_based - 1,
                        },
                    )
                )
        if docs:
            return docs

    return [
        Document(
            page_content=text,
            metadata={"source": filename, "parser": "docling", "page": 0},
        )
    ]


def docling_available() -> bool:
    """运行时检测 docling 是否已安装。"""
    try:
        import docling  # noqa: F401

        return True
    except ImportError:
        return False


def load_documents_with_docling(data: bytes, filename: str, ext: str) -> list[Document]:
    """将字节写入临时文件后交给 Docling 转换。"""
    from docling.document_converter import DocumentConverter

    suffix = _SUFFIX_BY_EXT.get(ext, ext if ext.startswith(".") else f".{ext}")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        converter = DocumentConverter()
        result = converter.convert(tmp_path)
        dl_doc = result.document
        markdown = dl_doc.export_to_markdown(
            page_break_placeholder=PAGE_BREAK_PLACEHOLDER,
        )
        if not (markdown or "").strip():
            raise ValueError("Docling 未提取到有效文本")
        return markdown_pages_to_documents(
            markdown,
            filename=filename,
            dl_doc=dl_doc,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
