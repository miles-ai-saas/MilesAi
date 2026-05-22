"""兼容转发 → app.rag.parse.loaders。"""

from app.rag.parse.loaders import documents_to_plain_text, load_documents_from_bytes

__all__ = ["documents_to_plain_text", "load_documents_from_bytes"]
