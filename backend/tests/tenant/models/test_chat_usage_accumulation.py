"""模型用量累计 ContextVar 测试。"""

from app.tenant.models.services.usage import (
    begin_chat_usage_accumulation,
    end_chat_usage_accumulation,
    get_chat_usage_totals,
)
from app.tenant.models.services import usage as usage_mod


def test_chat_usage_accumulation():
    token = begin_chat_usage_accumulation()
    try:
        usage_mod._chat_usage_acc.set((120, 30))
        assert get_chat_usage_totals() == (120, 30)
    finally:
        end_chat_usage_accumulation(token)
    assert get_chat_usage_totals() == (0, 0)
