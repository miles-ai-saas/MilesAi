"""向量化模型调用策略（模型类型校验）。"""

from __future__ import annotations

from miles_ai.integrations.embeddings.constants import INVOKE_MODE_CLIP
from miles_ai.integrations.embeddings.model_meta import invoke_mode_from_model
from miles_common.exceptions import BadRequestError


def ensure_clip_model(model) -> None:
    """校验模型为 CLIP 视觉向量化类型；否则抛 ``BadRequestError``。"""
    if invoke_mode_from_model(model) != INVOKE_MODE_CLIP:
        raise BadRequestError(f"模型「{model.name}」不是 CLIP 视觉向量化模型")
