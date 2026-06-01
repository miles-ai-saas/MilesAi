"""工作包里程碑 schemas。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class BizMilestoneCreate:
    title: str
    due_date: Optional[str] = None
    sort_order: int = 0


@dataclass
class BizMilestoneUpdate:
    title: Optional[str] = None
    due_date: Optional[str] = None
    completed_at: Optional[str] = None
    sort_order: Optional[int] = None


@dataclass
class BizMilestoneOut:
    id: UUID
    project_id: UUID
    work_package_id: UUID
    title: str
    due_date: Optional[str] = None
    completed_at: Optional[str] = None
    sort_order: int = 0


@dataclass
class BizMilestoneDueOut:
    id: UUID
    project_id: UUID
    project_name: str
    work_package_id: UUID
    work_package_name: str
    title: str
    due_date: Optional[str] = None
    overdue: bool = False
