"""项目 AI 上下文单元测试。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.biz.services.project_ai import ProjectAiContextService
from app.models.biz.enums import ConfidentialityLevel
from tests.conftest import make_tenant_ctx


@pytest.mark.asyncio
async def test_ai_context_disables_rag_for_restricted_client():
    ctx = make_tenant_ctx()
    project_id = uuid4()
    client_id = uuid4()

    project = MagicMock()
    project.id = project_id
    project.tenant_id = ctx.tenant_id
    project.client_id = client_id
    project.name = "涉密展馆"
    project.status = "active"
    project.description = None

    client = MagicMock()
    client.name = "涉密单位"
    client.confidentiality_level = ConfidentialityLevel.RESTRICTED.value

    db = AsyncMock()
    svc = ProjectAiContextService(db, ctx)
    svc.project_repo.get_by_id = AsyncMock(return_value=project)
    svc.client_repo.get_by_id = AsyncMock(return_value=client)
    svc.project_repo.get_work_packages = AsyncMock(return_value=[])
    svc.deliverable_repo.list_by_project = AsyncMock(return_value=[])

    out = await svc.get_ai_context(project_id)
    assert out.rag_enabled is False
    assert "涉密" in out.context_text


@pytest.mark.asyncio
async def test_ai_context_retrospective_when_delivered():
    ctx = make_tenant_ctx()
    project_id = uuid4()

    project = MagicMock()
    project.id = project_id
    project.tenant_id = ctx.tenant_id
    project.client_id = uuid4()
    project.name = "完成项目"
    project.status = "delivered"
    project.description = None

    client = MagicMock()
    client.name = "客户A"
    client.confidentiality_level = ConfidentialityLevel.NORMAL.value

    deliverable = MagicMock()
    deliverable.name = "最终方案"
    deliverable.status = "accepted"

    db = AsyncMock()
    svc = ProjectAiContextService(db, ctx)
    svc.project_repo.get_by_id = AsyncMock(return_value=project)
    svc.client_repo.get_by_id = AsyncMock(return_value=client)
    svc.project_repo.get_work_packages = AsyncMock(return_value=[])
    svc.deliverable_repo.list_by_project = AsyncMock(return_value=[deliverable])

    out = await svc.get_ai_context(project_id)
    assert out.retrospective_available is True
    assert out.retrospective_prompt and "结项复盘" in out.retrospective_prompt
