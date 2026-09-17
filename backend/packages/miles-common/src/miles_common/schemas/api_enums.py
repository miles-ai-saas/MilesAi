"""平台与模型目录 API 侧枚举声明。

与 ORM 侧 ``miles_core.models.platform.tenant``、``miles_core.models.model.catalog`` 逐字同形
（成员名/顺序/值），因 API 声明层不得依赖 ORM 模块
（``.importlinter`` 契约 ``api-layer-no-orm``）而独立声明；两侧一致性由
``tests/models/test_api_enum_parity.py`` 守卫。
"""

import enum


class TenantStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"


class ModelVendor(enum.StrEnum):
    DEEPSEEK = "deepseek"
    DOUBAO = "doubao"
    QWEN = "qwen"
    OPENAI = "openai"
    OTHER = "other"


class ModelCapabilityType(enum.StrEnum):
    LLM = "llm"
    REASONING = "reasoning"
    VISION = "vision"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    IMAGE_GEN = "image_gen"
    VIDEO_GEN = "video_gen"
    ASR = "asr"
    TTS = "tts"
    OTHER = "other"
