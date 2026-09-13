"""CLIP 视觉向量化的纯校验与谓词（embedding 解析见 L1 kb 域）。"""

from __future__ import annotations

from miles_ai.integrations.embeddings.constants import INVOKE_MODE_CLIP
from miles_ai.integrations.embeddings.model_meta import invoke_mode_from_model
from miles_ai.rag.parse.media import is_image_file
from miles_common.exceptions import BadRequestError
from miles_core.models.kb import KnowledgeBase


def ensure_clip_model(model) -> None:
    """校验模型为 CLIP 视觉向量化类型；否则抛 ``BadRequestError``。"""
    if invoke_mode_from_model(model) != INVOKE_MODE_CLIP:
        raise BadRequestError(f"模型「{model.name}」不是 CLIP 视觉向量化模型")


def should_use_visual_image_embedding(
    kb: KnowledgeBase,
    filename: str,
    mime_type: str,
) -> bool:
    """KB 绑定了视觉向量化模型且文件为图片时返回 ``True``。"""
    return kb.visual_embedding_model_config_id is not None and is_image_file(filename, mime_type)
