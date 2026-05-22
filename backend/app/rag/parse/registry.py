"""文件解析注册表：统一走 load_documents_from_bytes + chunk。"""

from app.common.exceptions import BadRequestError
from app.rag.chunk import chunk_documents
from app.rag.parse.loaders import documents_to_plain_text, load_documents_from_bytes


def parse_file(data: bytes, filename: str, mime_type: str) -> str:
    try:
        docs = load_documents_from_bytes(data, filename, mime_type)
    except BadRequestError:
        raise

    pieces = chunk_documents(docs)
    if pieces:
        return "\n\n".join(p.content for p in pieces)
    return documents_to_plain_text(docs)
