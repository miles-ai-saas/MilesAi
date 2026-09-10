"""模型 API Key 格式校验的 L1 兼容入口。

实现已下沉中立 ``app.common.api_key``（供运营端与租户域复用）；本模块仅
re-export，保持既有 ``app.tenant.models.services.api_key_validation`` import 稳定。
"""

from __future__ import annotations

from app.common.api_key import (
    assert_usable_api_key,
    normalize_api_key,
    validate_api_key,
)

__all__ = [
    "assert_usable_api_key",
    "normalize_api_key",
    "validate_api_key",
]
