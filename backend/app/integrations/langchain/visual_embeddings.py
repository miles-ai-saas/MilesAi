"""CLIP 视觉向量化的纯校验与谓词（embedding 解析见 L1 kb 域）。"""

from __future__ import annotations

from app.common.exceptions import BadRequestError
from app.integrations.embeddings.constants import INVOKE_MODE_CLIP
from app.integrations.embeddings.model_meta import invoke_mode_from_model
from app.models.kb import KnowledgeBase
from app.rag.parse.media import is_image_file


def ensure_clip_model(model) -> None:
    if invoke_mode_from_model(model) != INVOKE_MODE_CLIP:
        raise BadRequestError(f"模型「{model.name}」不是 CLIP 视觉向量化模型")


def should_use_visual_image_embedding(
    kb: KnowledgeBase,
    filename: str,
    mime_type: str,
) -> bool:
    return kb.visual_embedding_model_config_id is not None and is_image_file(filename, mime_type)
