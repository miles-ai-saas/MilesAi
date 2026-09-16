"""模型目录枚举与常量（供应商、能力类型、发布态、内置 embedding 默认 code）。"""

import enum


# 模型供应商。
class ModelVendor(enum.StrEnum):
    DEEPSEEK = "deepseek"
    DOUBAO = "doubao"
    QWEN = "qwen"
    OPENAI = "openai"
    OTHER = "other"


# 模型能力类型（用于目录分类与筛选）。
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


# 目录 / 筛选 UI 展示顺序（与 MODEL_TYPE_LABELS 一致）
CATALOG_MODEL_TYPES: tuple[ModelCapabilityType, ...] = (
    ModelCapabilityType.LLM,
    ModelCapabilityType.REASONING,
    ModelCapabilityType.VISION,
    ModelCapabilityType.EMBEDDING,
    ModelCapabilityType.RERANK,
    ModelCapabilityType.IMAGE_GEN,
    ModelCapabilityType.VIDEO_GEN,
    ModelCapabilityType.ASR,
    ModelCapabilityType.TTS,
    ModelCapabilityType.OTHER,
)


# 模型发布状态。
class ModelPublishStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


VENDOR_LABELS: dict[str, str] = {
    ModelVendor.DEEPSEEK.value: "深度求索",
    ModelVendor.DOUBAO.value: "豆包",
    ModelVendor.QWEN.value: "通义千问",
    ModelVendor.OPENAI.value: "OpenAI",
    ModelVendor.OTHER.value: "其它",
}

DEFAULT_API_BASES: dict[str, str] = {
    ModelVendor.DEEPSEEK.value: "https://api.deepseek.com/v1",
    ModelVendor.DOUBAO.value: "https://ark.cn-beijing.volces.com/api/v3",
    ModelVendor.QWEN.value: "https://dashscope.aliyuncs.com/compatible-mode/v1",
}

# DashScope 文本重排（与 chat/embedding 的 compatible-mode 不同）
DEFAULT_RERANK_API_ENDPOINTS: dict[str, str] = {
    ModelVendor.QWEN.value: ("https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"),
}

DEFAULT_RERANK_OPENAI_COMPAT_BASES: dict[str, str] = {
    ModelVendor.QWEN.value: "https://dashscope.aliyuncs.com/compatible-api/v1",
}

BUILTIN_EMBEDDING_DEFAULT_CODE = "bge-base-zh-v1.5"
BUILTIN_RERANK_DEFAULT_CODE = "qwen3-rerank"

MODEL_TYPE_LABELS: dict[str, str] = {
    ModelCapabilityType.LLM.value: "大语言模型",
    ModelCapabilityType.REASONING.value: "推理模型",
    ModelCapabilityType.VISION.value: "图像理解",
    ModelCapabilityType.EMBEDDING.value: "向量化",
    ModelCapabilityType.RERANK.value: "重排序",
    ModelCapabilityType.ASR.value: "语音识别",
    ModelCapabilityType.TTS.value: "语音合成",
    ModelCapabilityType.IMAGE_GEN.value: "图像生成",
    ModelCapabilityType.VIDEO_GEN.value: "视频生成",
    ModelCapabilityType.OTHER.value: "其它",
}
