"""入库时的视觉向量化决策（是否对图片走 CLIP 向量化）。"""

from __future__ import annotations

from miles_ai.rag.parse.media import is_image_file
from miles_core.models.kb import KnowledgeBase


def should_use_visual_image_embedding(
    kb: KnowledgeBase,
    filename: str,
    mime_type: str,
) -> bool:
    """KB 绑定了视觉向量化模型且文件为图片时返回 ``True``。"""
    return kb.visual_embedding_model_config_id is not None and is_image_file(filename, mime_type)
