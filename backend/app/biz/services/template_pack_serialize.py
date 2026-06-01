"""服务线模板包序列化。"""

from __future__ import annotations

from app.biz.schemas.template_pack import BizServiceLineTemplatePackOut
from app.biz.services.meta import SERVICE_LINES
from app.biz.services.service_line_template import parse_stage_names
from app.models.biz.template_pack import BizServiceLineTemplatePack


def pack_to_out(row: BizServiceLineTemplatePack, *, viewer_tenant_id=None) -> BizServiceLineTemplatePackOut:
    labels = {item.key: item.label for item in SERVICE_LINES}
    tags = row.tags if isinstance(row.tags, list) else []
    is_mine = viewer_tenant_id is not None and row.tenant_id == viewer_tenant_id
    return BizServiceLineTemplatePackOut(
        id=str(row.id),
        service_line=row.service_line,
        service_line_label=labels.get(row.service_line, row.service_line),
        name=row.name,
        description=row.description,
        stages=parse_stage_names(row.stages),
        ai_config=row.ai_config if isinstance(row.ai_config, dict) else {},
        publisher_name=row.publisher_name,
        publisher_type=row.publisher_type,
        publisher_tenant_id=str(row.tenant_id) if row.tenant_id else None,
        tags=[str(t) for t in tags],
        is_featured=row.is_featured,
        is_active=row.is_active,
        install_count=row.install_count or 0,
        status=row.status,
        review_note=row.review_note,
        submitted_at=row.submitted_at.isoformat() if row.submitted_at else None,
        reviewed_at=row.reviewed_at.isoformat() if row.reviewed_at else None,
        is_mine=is_mine,
    )
