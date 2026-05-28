"""敏感词拦截日志查询。"""

from sqlalchemy import func, select
from app.common.schema import PageParams, PageResult
from app.core.tenant import tenant_filters
from app.tenant.compliance.models import InterceptLog
from app.tenant.compliance.schemas.compliance import InterceptLogOut


class InterceptLogMixin:
    """敏感词拦截日志查询。"""

    async def list_logs(self, params: PageParams) -> PageResult[InterceptLogOut]:
        """分页查询拦截日志。"""
        filters = tenant_filters(self.ctx, InterceptLog.tenant_id)
        total = await self.db.scalar(select(func.count()).select_from(InterceptLog).where(*filters))
        stmt = select(InterceptLog).where(*filters).order_by(InterceptLog.created_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[InterceptLogOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )
