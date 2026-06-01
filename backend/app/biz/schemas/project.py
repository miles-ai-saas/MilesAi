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
