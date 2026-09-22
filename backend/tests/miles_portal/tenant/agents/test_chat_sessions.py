"""对话会话持久化辅助函数测试。"""

from miles_portal.tenant.agents.services.chat_sessions import _derive_title


def test_derive_title_from_first_message():
    assert _derive_title("新对话", "你好世界") == "你好世界"
    assert _derive_title("已有标题", "新消息") == "已有标题"
    long_text = "x" * 40
    assert _derive_title("新对话", long_text).endswith("…")
