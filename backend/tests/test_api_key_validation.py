"""API Key 格式校验单元测试。"""

import pytest

from app.common.exceptions import BadRequestError
from app.tenant.models.services.api_key_validation import validate_api_key


def test_validate_accepts_dashscope_key():
    assert validate_api_key("sk-abc1234567890", vendor="qwen") == "sk-abc1234567890"


def test_validate_rejects_error_text():
    with pytest.raises(BadRequestError, match="不像有效密钥"):
        validate_api_key("Error: Network Error Source lib/api.ts", vendor="qwen")


def test_validate_rejects_digits_only():
    with pytest.raises(BadRequestError, match="纯数字"):
        validate_api_key("02605251009242266674", vendor="qwen")


def test_validate_rejects_qwen_without_sk_prefix():
    with pytest.raises(BadRequestError, match="sk-"):
        validate_api_key("not-a-real-key-value", vendor="qwen")
