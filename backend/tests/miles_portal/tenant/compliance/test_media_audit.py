"""入站图片视觉审核：非图片跳过、unsafe 拦截、无模型 fail-open。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_common.schemas.media import MediaRefIn
from miles_portal.tenant.compliance.models import SensitiveAction
from miles_portal.tenant.compliance.services.compliance.intercept import ComplianceInterceptMixin
from miles_portal.tenant.compliance.services.compliance.media_audit import check_media_safety


class _Svc(ComplianceInterceptMixin):
    def __init__(self) -> None:
        self.db = MagicMock()
        self.ctx = SimpleNamespace(tenant_id=uuid4(), user_id=uuid4())
        self.logged: list[dict] = []

    async def log_intercept(self, **kwargs):  # noqa: ANN003
        self.logged.append(kwargs)


@pytest.mark.asyncio
async def test_check_media_safety_skips_non_image():
    aid = uuid4()
    att = SimpleNamespace(mime_type="audio/mpeg", filename="a.mp3")

    with patch(
        "miles_portal.tenant.compliance.services.compliance.media_audit.AttachmentService"
    ) as AttSvc:
        AttSvc.return_value.get = AsyncMock(return_value=att)
        out = await check_media_safety(aid, MagicMock(), SimpleNamespace(tenant_id=uuid4()))

    assert out["safe"] is True
    assert "非图片" in out["reason"]
    AttSvc.return_value.read_image_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_check_media_safety_unsafe_from_model():
    aid = uuid4()
    att = SimpleNamespace(mime_type="image/png", filename="x.png")
    ctx = SimpleNamespace(tenant_id=uuid4())

    with (
        patch(
            "miles_portal.tenant.compliance.services.compliance.media_audit.AttachmentService"
        ) as AttSvc,
        patch(
            "miles_portal.tenant.compliance.services.compliance.media_audit._pick_moderation_model",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(id=uuid4()),
        ),
        patch(
            "miles_portal.tenant.compliance.services.compliance.media_audit.resolve_model_for_invoke",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(id=uuid4()),
        ),
        patch(
            "miles_portal.tenant.compliance.services.compliance.media_audit.ainvoke_chat",
            new_callable=AsyncMock,
            return_value='{"safe": false, "category": "暴力", "reason": "含暴力内容"}',
        ),
        patch(
            "miles_portal.tenant.compliance.services.compliance.media_audit.ChatUsageSink",
            return_value=None,
        ),
    ):
        AttSvc.return_value.get = AsyncMock(return_value=att)
        AttSvc.return_value.read_image_bytes = AsyncMock(return_value=(b"\x89PNG", "image/png"))
        out = await check_media_safety(aid, MagicMock(), ctx)

    assert out["safe"] is False
    assert out["category"] == "暴力"


@pytest.mark.asyncio
async def test_check_media_input_blocks_unsafe():
    svc = _Svc()
    aid = uuid4()

    with patch(
        "miles_portal.tenant.compliance.services.compliance.intercept.check_media_safety",
        new_callable=AsyncMock,
        return_value={"safe": False, "category": "色情", "reason": "违规", "attachment_id": str(aid)},
    ):
        with pytest.raises(BadRequestError, match="内容安全审核"):
            await svc.check_media_input([MediaRefIn(attachment_id=aid)], module="agent_chat")

    assert len(svc.logged) == 1
    assert svc.logged[0]["action"] == SensitiveAction.BLOCK
    assert svc.logged[0]["matched_word"] == "色情"


@pytest.mark.asyncio
async def test_check_media_input_noop_without_media():
    svc = _Svc()
    await svc.check_media_input(None, module="agent_chat")
    await svc.check_media_input([], module="agent_chat")
    assert svc.logged == []


@pytest.mark.asyncio
async def test_check_media_input_pass_when_safe():
    svc = _Svc()
    aid = uuid4()
    with patch(
        "miles_portal.tenant.compliance.services.compliance.intercept.check_media_safety",
        new_callable=AsyncMock,
        return_value={"safe": True, "category": "none", "reason": "ok", "attachment_id": str(aid)},
    ):
        await svc.check_media_input([aid], module="flow_run")
    assert svc.logged == []
