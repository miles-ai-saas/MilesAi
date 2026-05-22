"""知识库向量化规格目录（创建 KB 时选择，创建后不可改）。"""

from __future__ import annotations

from dataclasses import dataclass

from app.common.exceptions import BadRequestError


@dataclass(frozen=True)
class EmbeddingProfileSpec:
    id: str
    label: str
    backend: str  # local | litellm
    model_name: str
    dimension: int


EMBEDDING_PROFILES: dict[str, EmbeddingProfileSpec] = {
    "local-minilm": EmbeddingProfileSpec(
        id="local-minilm",
        label="本地 MiniLM（384 维）",
        backend="local",
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
    ),
    "dashscope-v3": EmbeddingProfileSpec(
        id="dashscope-v3",
        label="通义 text-embedding-v3（1024 维）",
        backend="litellm",
        model_name="dashscope/text-embedding-v3",
        dimension=1024,
    ),
}


def get_embedding_profile(profile_id: str) -> EmbeddingProfileSpec:
    key = (profile_id or "").strip()
    spec = EMBEDDING_PROFILES.get(key)
    if not spec:
        allowed = ", ".join(sorted(EMBEDDING_PROFILES))
        raise BadRequestError(f"不支持的 embedding_profile: {profile_id!r}，可选: {allowed}")
    return spec


def list_embedding_profiles() -> list[EmbeddingProfileSpec]:
    return list(EMBEDDING_PROFILES.values())


def default_embedding_profile_id() -> str:
    from app.core.config import get_settings

    s = get_settings()
    if s.embedding_backend.strip().lower() == "litellm":
        if "dashscope-v3" in EMBEDDING_PROFILES:
            return "dashscope-v3"
    return "local-minilm"
