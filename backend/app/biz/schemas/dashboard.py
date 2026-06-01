"""仪表盘 schemas。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RecentProjectItem:
    id: str
    name: str
    status: str
    client_name: str


@dataclass
class DueMilestoneItem:
    id: str
    project_id: str
    project_name: str
    title: str
    due_date: str
    overdue: bool


@dataclass
class DashboardSummaryOut:
    total_clients: int = 0
    active_projects: int = 0
    pending_deliverables: int = 0
    work_packages_in_progress: int = 0
    due_milestones: int = 0
    due_milestone_items: list[DueMilestoneItem] = field(default_factory=list)
    recent_projects: list[RecentProjectItem] = field(default_factory=list)
