"""模板市场分类与标签校验测试。"""

import pytest

from app.biz.services.template_pack_meta import (
    default_category_for_service_line,
    normalize_customer_type_tags,
    validate_category,
)
from app.common.exceptions import BadRequestError


def test_default_category_for_service_line():
    assert default_category_for_service_line("event") == "event"
    assert default_category_for_service_line("brand_identity") == "brand"
    assert default_category_for_service_line("unknown") == "general"


def test_validate_category_rejects_unknown():
    with pytest.raises(BadRequestError):
        validate_category("invalid")


def test_normalize_customer_type_tags():
    assert normalize_customer_type_tags(["government", "enterprise"]) == ["government", "enterprise"]
    assert normalize_customer_type_tags(["government", "government"]) == ["government"]


def test_normalize_customer_type_tags_rejects_free_text():
    with pytest.raises(BadRequestError):
        normalize_customer_type_tags(["政府"])
