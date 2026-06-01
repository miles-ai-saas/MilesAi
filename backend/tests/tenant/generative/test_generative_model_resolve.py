"""生成模型默认选取（厂商优先级）。"""

from app.integrations.generative.registry import (
    default_image_invoke_mode,
    default_video_invoke_mode,
)
from app.models.model import ModelConfig
from app.models.model.catalog import ModelCapabilityType, ModelVendor
from uuid import uuid4


def _model(vendor: str, model_type: str) -> ModelConfig:
    return ModelConfig(
        id=uuid4(),
        tenant_id=uuid4(),
        name=vendor,
        provider=vendor,
        model_name="m",
        model_code="m",
        vendor=vendor,
        model_type=model_type,
        extra={},
    )


def test_default_video_invoke_mode_qwen_first():
    assert default_video_invoke_mode(_model(ModelVendor.QWEN.value, ModelCapabilityType.VIDEO_GEN.value)) == "dashscope_t2v"
    assert default_video_invoke_mode(_model(ModelVendor.DOUBAO.value, ModelCapabilityType.VIDEO_GEN.value)) == "volcengine_video"
    assert default_video_invoke_mode(_model(ModelVendor.OPENAI.value, ModelCapabilityType.VIDEO_GEN.value)) == "dashscope_t2v"


def test_default_image_invoke_mode_qwen_vs_openai():
    assert default_image_invoke_mode(_model(ModelVendor.QWEN.value, ModelCapabilityType.IMAGE_GEN.value)) == "dashscope_t2i"
    assert default_image_invoke_mode(_model(ModelVendor.OPENAI.value, ModelCapabilityType.IMAGE_GEN.value)) == "openai_images"
