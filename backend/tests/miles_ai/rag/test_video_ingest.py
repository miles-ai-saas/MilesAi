"""视频解析与 media_types 检索过滤测试。"""

from miles_ai.rag.parse.upload_policy import is_kb_upload_allowed, kb_upload_accept_attribute
from miles_ai.rag.parse.video_parser import parse_video


def test_video_extensions_allowed():
    assert is_kb_upload_allowed("clip.mp4", "video/mp4")
    assert is_kb_upload_allowed("movie.mov", "video/quicktime")
    assert is_kb_upload_allowed("demo.webm", "video/webm")


def test_accept_attribute_includes_video():
    accept = kb_upload_accept_attribute()
    assert ".mp4" in accept
    assert ".mov" in accept


def test_parse_video_placeholder_without_ffmpeg():
    text = parse_video(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64, "sample.mp4")
    assert "视频" in text
