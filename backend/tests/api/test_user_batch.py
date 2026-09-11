"""用户批量操作请求体验证。"""

import pytest
from pydantic import ValidationError
from uuid import uuid4

from miles_portal.tenant.system.schemas.user import UserBatchRequest


def test_batch_assign_roles_requires_role_ids():
    with pytest.raises(ValidationError):
        UserBatchRequest(user_ids=[uuid4()], action="assign_roles")


def test_batch_disable_ok():
    body = UserBatchRequest(user_ids=[uuid4(), uuid4()], action="disable")
    assert body.action == "disable"
    assert len(body.user_ids) == 2
