"""项目与工作包 API schemas。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


# ── project ──

@dataclass
class WorkPackageCreate:
    service_line: str
    name: str
    owner_id: Optional[UUID] = None
    budget: Optional[float] = None
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None


@dataclass
class BizProjectCreate:
    client_id: UUID
    name: str
    code: Optional[str] = None
    owner_id: Optional[UUID] = None
    description: Optional[str] = None
    total_budget: Optional[float] = None
    work_packages: list[WorkPackageCreate] = field(default_factory=list)


@dataclass
class BizProjectUpdate:
    name: Optional[str] = None
    code: Optional[str] = None
    status: Optional[str] = None
    owner_id: Optional[UUID] = None
    description: Optional[str] = None
    total_budget: Optional[float] = None


# ── work package ──

@dataclass
class BizWorkPackageCreate:
    service_line: str
    name: str
    owner_id: Optional[UUID] = None
    budget: Optional[float] = None
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None


@dataclass
class BizWorkPackageUpdate:
    name: Optional[str] = None
    stage: Optional[str] = None
    status: Optional[str] = None
    owner_id: Optional[UUID] = None
    budget: Optional[float] = None
    actual_cost: Optional[float] = None
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None


@dataclass
class BizWorkPackageOut:
    id: UUID
    project_id: UUID
    service_line: str
    name: str
    stage: Optional[str] = None
    stage_index: int = 0
    status: str = "pending"
    owner_id: Optional[UUID] = None
    budget: Optional[float] = None
    actual_cost: Optional[float] = None
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None


@dataclass
class BizWorkPackageKanbanOut(BizWorkPackageOut):
    project_name: str = ""
    client_name: str = ""


# ── project out ──

@dataclass
class BizProjectOut:
    id: UUID
    client_id: UUID
    name: str
    status: str
    code: Optional[str] = None
    owner_id: Optional[UUID] = None
    description: Optional[str] = None
    total_budget: Optional[float] = None
    work_packages: list[BizWorkPackageOut] = field(default_factory=list)


@dataclass
class BizProjectMemberOut:
    project_id: UUID
    user_id: UUID
    role_in_project: str
    username: Optional[str] = None


@dataclass
class BizProjectMemberCreate:
    user_id: UUID
    role_in_project: str = "viewer"


@dataclass
class BizWorkPackageCostLine:
    id: UUID
    name: str
    service_line: str
    budget: Optional[float] = None
    actual_cost: Optional[float] = None
    variance: Optional[float] = None


@dataclass
class BizProjectCostSummaryOut:
    project_id: UUID
    total_budget: Optional[float] = None
    work_package_budget_total: Optional[float] = None
    work_package_actual_total: Optional[float] = None
    budget_variance: Optional[float] = None
    work_packages: list[BizWorkPackageCostLine] = field(default_factory=list)


@dataclass
class BizProjectCloseOut:
    id: UUID
    status: str


@dataclass
class BizArchiveCaseRequest:
    kb_id: UUID
    run_parse: bool = True


@dataclass
class BizArchiveCaseOut:
    project_id: UUID
    kb_id: UUID
    archived_count: int
    document_ids: list[UUID] = field(default_factory=list)


@dataclass
class BizArchivableDeliverableOut:
    id: UUID
    name: str
    version: Optional[str] = None
    has_attachment: bool = False


@dataclass
class BizClosePreviewOut:
    project_id: UUID
    project_name: str
    status: str
    client_confidentiality: str
    pending_deliverables: int
    submitted_deliverables: int
    incomplete_work_packages: int
    archivable_deliverables: list[BizArchivableDeliverableOut] = field(default_factory=list)
    can_archive: bool = False
    archive_blocked_reason: Optional[str] = None


@dataclass
class BizCloseWizardRequest:
    kb_id: Optional[UUID] = None
    deliverable_ids: list[UUID] = field(default_factory=list)
    run_parse: bool = True
    skip_archive: bool = False
    confirm_desensitized: bool = False


@dataclass
class BizCloseWizardOut:
    project_id: UUID
    status: str
    archived_count: int = 0
    document_ids: list[UUID] = field(default_factory=list)
