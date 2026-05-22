"""模型目录枚举与常量（供应商、能力类型、发布态、内置 embedding 默认 code）。"""

import enum


class ModelVendor(str, enum.Enum):
    DEEPSEEK = "deepseek"
    DOUBAO = "doubao"
    QWEN = "qwen"
    OPENAI = "openai"
    OTHER = "other"


class ModelCapabilityType(str, enum.Enum):
    LLM = "llm"
    REASONING = "reasoning"
    VISION = "vision"
    EMBEDDING = "embedding"
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
    ModelCapabilityType.IMAGE_GEN,
    ModelCapabilityType.VIDEO_GEN,
    ModelCapabilityType.ASR,
    ModelCapabilityType.TTS,
    ModelCapabilityType.OTHER,
)


class ModelPublishStatus(str, enum.Enum):
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

BUILTIN_EMBEDDING_DEFAULT_CODE = "bge-base-zh-v1.5"

MODEL_TYPE_LABELS: dict[str, str] = {
    ModelCapabilityType.LLM.value: "大语言模型",
    ModelCapabilityType.REASONING.value: "推理模型",
    ModelCapabilityType.VISION.value: "图像理解",
    ModelCapabilityType.EMBEDDING.value: "向量化",
    ModelCapabilityType.ASR.value: "语音识别",
    ModelCapabilityType.TTS.value: "语音合成",
    ModelCapabilityType.IMAGE_GEN.value: "图像生成",
    ModelCapabilityType.VIDEO_GEN.value: "视频生成",
    ModelCapabilityType.OTHER.value: "其它",
}
