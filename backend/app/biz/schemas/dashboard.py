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
class DashboardSummaryOut:
    total_clients: int = 0
    active_projects: int = 0
    pending_deliverables: int = 0
    work_packages_in_progress: int = 0
    recent_projects: list[RecentProjectItem] = field(default_factory=list)
