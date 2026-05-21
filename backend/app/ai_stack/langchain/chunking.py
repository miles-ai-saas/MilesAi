"""LangChain 文本分片。"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings


def split_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    settings = get_settings()
    size = chunk_size if chunk_size is not None else settings.default_chunk_size
    ov = overlap if overlap is not None else settings.default_chunk_overlap
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=ov,
        length_function=len,
    )
    return splitter.split_text(text)
