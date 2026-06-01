"""结项向导单元测试。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.biz.schemas.project import BizCloseWizardRequest
from app.biz.services.project_close import ProjectCloseService
from app.common.exceptions import BadRequestError
from tests.conftest import make_tenant_ctx


@pytest.mark.asyncio
async def test_close_preview_counts():
    ctx = make_tenant_ctx()
    project_id = uuid4()
    client_id = uuid4()

    project = MagicMock()
    project.id = project_id
    project.name = "测试项目"
    project.status = "active"
    project.client_id = client_id
    project.tenant_id = ctx.tenant_id

    client = MagicMock()
    client.confidentiality_level = "normal"

    d1 = MagicMock(status="submitted")
    d2 = MagicMock(status="accepted", attachment_id=uuid4(), kb_document_id=None, id=uuid4(), name="方案", version="v1")
    wp = MagicMock(status="in_progress")

    db = AsyncMock()
    svc = ProjectCloseService(db, ctx)
    svc.project_repo.get_by_id = AsyncMock(return_value=project)
    svc.client_repo.get_by_id = AsyncMock(return_value=client)
    svc.deliverable_repo.list_by_project = AsyncMock(return_value=[d1, d2])
    svc.project_repo.get_work_packages = AsyncMock(return_value=[wp])

    preview = await svc.get_close_preview(project_id)
    assert preview.submitted_deliverables == 1
    assert preview.incomplete_work_packages == 1
    assert preview.can_archive is True
    assert len(preview.archivable_deliverables) == 1


@pytest.mark.asyncio
async def test_close_wizard_requires_desensitized_confirm():
    ctx = make_tenant_ctx()
    project_id = uuid4()

    db = AsyncMock()
    svc = ProjectCloseService(db, ctx)
    svc.get_close_preview = AsyncMock(return_value=MagicMock(
        status="active",
        client_confidentiality="normal",
        archivable_deliverables=[MagicMock(id=uuid4())],
    ))

    with pytest.raises(BadRequestError, match="脱敏"):
        await svc.execute_close_wizard(
            project_id,
            BizCloseWizardRequest(kb_id=uuid4(), deliverable_ids=[uuid4()], confirm_desensitized=False),
        )
