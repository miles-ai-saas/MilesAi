"""万相生视频首尾帧 media 构建。"""

import pytest

from miles_common.exceptions import BadRequestError
from miles_integrations.generative.video.providers.dashscope_wan import _build_media


def test_build_media_first_only():
    media = _build_media("data:image/png;base64,a", None)
    assert media == [{"type": "first_frame", "url": "data:image/png;base64,a"}]


def test_build_media_first_and_last():
    media = _build_media("data:image/png;base64,a", "data:image/png;base64,b")
    assert len(media) == 2
    assert media[0]["type"] == "first_frame"
    assert media[1]["type"] == "last_frame"


def test_build_media_last_without_first():
    with pytest.raises(BadRequestError, match="首尾帧"):
        _build_media(None, "data:image/png;base64,b")
