"""服务线阶段模板解析。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.service_line_template import ServiceLineTemplateRepository


def parse_stage_names(stages: list | dict | None) -> list[str]:
    """将 JSONB stages 规范化为阶段名称列表。"""
    if not stages:
        return []
    if isinstance(stages, list):
        names: list[str] = []
        for item in stages:
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    names.append(name.strip())
        return names
    if isinstance(stages, dict):
        items = stages.get("items")
        if isinstance(items, list):
            return parse_stage_names(items)
    return []


def initial_stage(stages: list | dict | None) -> tuple[str | None, int]:
    """返回工作包创建时的初始阶段名与序号。"""
    names = parse_stage_names(stages)
    if not names:
        return None, 0
    return names[0], 0


class ServiceLineTemplateService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = ServiceLineTemplateRepository(db)

    async def resolve_initial_stage(self, tenant_id: UUID, service_line: str) -> tuple[str | None, int]:
        row = await self.repo.get_active_template(tenant_id, service_line)
        if not row:
            return None, 0
        return initial_stage(row.stages)
