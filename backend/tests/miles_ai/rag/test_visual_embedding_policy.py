"""KB 视觉向量化入库策略测试（rag.pipeline.visual_policy）。"""

from uuid import uuid4

from miles_ai.rag.pipeline.visual_policy import should_use_visual_image_embedding
from miles_core.models.kb import KnowledgeBase


def test_should_use_visual_image_embedding():
    kb = KnowledgeBase(
        id=uuid4(),
        tenant_id=uuid4(),
        name="kb",
        embedding_model_config_id=uuid4(),
        visual_embedding_model_config_id=uuid4(),
    )
    assert should_use_visual_image_embedding(kb, "photo.jpg", "image/jpeg") is True
    assert should_use_visual_image_embedding(kb, "doc.pdf", "application/pdf") is False
