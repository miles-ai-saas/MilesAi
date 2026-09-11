"""媒体资产登记与升格规则。"""

from miles_ai.integrations.generative.constants import PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED
from miles_portal.tenant.media_assets.services.media_asset import (
    SOURCE_AGENT_TOOL,
    SOURCE_FLOW_NODE,
    _kind_from_mime,
    _source_from_purpose,
)


def test_kind_from_mime():
    assert _kind_from_mime("image/png") == "image"
    assert _kind_from_mime("video/mp4") == "video"


def test_source_from_purpose():
    assert _source_from_purpose(PURPOSE_CHAT_GENERATED) == SOURCE_AGENT_TOOL
    assert _source_from_purpose(PURPOSE_FLOW_GENERATED) == SOURCE_FLOW_NODE


def test_video_promote_builds_markdown():
    from uuid import uuid4

    from miles_core.models.media.attachment import Attachment
    from miles_core.models.media.media_asset import MediaAsset
    from miles_portal.tenant.media_assets.schemas.media_asset import PromoteToKbRequest
    from miles_portal.tenant.media_assets.services.media_asset import MediaAssetService

    row = MediaAsset(
        id=uuid4(),
        tenant_id=uuid4(),
        attachment_id=uuid4(),
        kind="video",
        source="agent_tool",
        prompt="海浪慢镜头",
        created_by=uuid4(),
    )
    att = Attachment(
        id=row.attachment_id,
        tenant_id=row.tenant_id,
        uploaded_by=row.created_by,
        filename="clip.mp4",
        mime_type="video/mp4",
        file_size=1024,
        object_bucket="b",
        object_key="k",
        purpose="chat_generated",
    )
    svc = MediaAssetService.__new__(MediaAssetService)
    content, filename, mime = svc._build_video_promote_document(row, att, PromoteToKbRequest(kb_id=uuid4()))
    text = content.decode("utf-8")
    assert mime == "text/markdown"
    assert filename.endswith(".md")
    assert "海浪慢镜头" in text
    assert str(att.id) in text
