"""视频封面抽取。"""

from unittest.mock import patch

from miles_ai.integrations.generative.video.cover import extract_video_cover_jpeg
from miles_portal.tenant.media_assets.schemas.media_asset import MediaAssetOut


def test_extract_video_cover_without_ffmpeg():
    with patch("miles_ai.integrations.generative.video.cover.shutil.which", return_value=None):
        assert extract_video_cover_jpeg(b"\x00\x00\x00\x18ftypmp42") is None


def test_media_asset_out_has_cover_fields():
    assert "cover_attachment_id" in MediaAssetOut.model_fields
    assert "cover_attachment" in MediaAssetOut.model_fields
