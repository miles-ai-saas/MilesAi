"""媒体资产登记与升格规则。"""

from app.integrations.generative.persist import PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED
from app.tenant.media_assets.services.media_asset import (
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
