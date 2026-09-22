"""CLIP 视觉向量化（``invoke_mode=clip``）。"""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO

from miles_core.models.model import ModelConfig


@lru_cache(maxsize=2)
def _load_clip(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _encode_images(model_name: str, images: list[bytes]) -> list[list[float]]:
    from PIL import Image

    if not images:
        return []
    encoder = _load_clip(model_name)
    pil_images = [Image.open(BytesIO(raw)).convert("RGB") for raw in images]
    vectors = encoder.encode(pil_images, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


class ClipEmbeddingProvider:
    """registry 注册的 CLIP Provider；文本与图像向量处于同一语义空间。"""

    def embed_texts(self, model: ModelConfig, texts: list[str]) -> list[list[float]]:
        """把文本编码到 CLIP 语义空间（向量已 L2 归一化，空输入返回空列表）。"""
        if not texts:
            return []
        encoder = _load_clip(model.model_name)
        vectors = encoder.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    def embed_images(self, model: ModelConfig, images: list[bytes]) -> list[list[float]]:
        """把图片字节编码到同一 CLIP 语义空间（供图文互检；空输入返回空列表）。"""
        return _encode_images(model.model_name, images)
