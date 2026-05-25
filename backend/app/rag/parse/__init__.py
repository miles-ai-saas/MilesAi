"""解析层对外导出：多模态类型判定与 vector_type（完整加载见 loaders.load_documents_from_bytes）。"""

from app.rag.parse.media import (
    file_extension,
    is_audio_file,
    is_image_file,
    vector_type_for_document,
)

__all__ = [
    "file_extension",
    "is_audio_file",
    "is_image_file",
    "vector_type_for_document",
]
