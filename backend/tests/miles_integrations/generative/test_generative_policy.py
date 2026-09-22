"""生图工具确认策略。"""

from miles_integrations.generative.policy import (
    image_tool_confirmation_message,
    is_high_resolution_image_size,
    needs_image_tool_confirmation,
)


def test_is_high_resolution_by_edge():
    assert is_high_resolution_image_size("1280x720") is True
    assert is_high_resolution_image_size("1024x1024") is False


def test_needs_confirmation_for_multi_image():
    assert needs_image_tool_confirmation({"size": "1024x1024", "n": 3}) is True
    assert needs_image_tool_confirmation({"size": "1024x1024", "n": 1}) is False


def test_confirmation_message_mentions_size():
    msg = image_tool_confirmation_message({"size": "1280x720", "n": 2})
    assert "1280x720" in msg
    assert "确认" in msg
