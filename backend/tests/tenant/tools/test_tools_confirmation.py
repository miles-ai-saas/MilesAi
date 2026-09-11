from miles_portal.tenant.tools.confirmation import ToolConfirmationRequired
from miles_portal.tenant.tools.builtin_registry import get_builtin


def test_builtin_get_current_datetime_requires_no_confirmation():
    meta = get_builtin("get_current_datetime")
    assert meta is not None
    assert meta["require_confirmation"] is False


def test_builtin_generate_video_requires_no_confirmation():
    meta = get_builtin("generate_video")
    assert meta is not None
    assert meta["require_confirmation"] is False


def test_confirmation_required_exception():
    exc = ToolConfirmationRequired("weather", "天气", "查天气", {"city": "bj"})
    assert exc.slug == "weather"
    assert "天气" in str(exc)
