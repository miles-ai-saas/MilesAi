"""商机 API schemas。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class BizOpportunityCreate:
    client_id: UUID
    name: str
    code: Optional[str] = None
    stage: str = "prospecting"
    expected_value: Optional[float] = None
    probability: Optional[int] = None
    expected_close_date: Optional[str] = None
    owner_id: Optional[UUID] = None
    description: Optional[str] = None


@dataclass
class BizOpportunityUpdate:
    name: Optional[str] = None
    code: Optional[str] = None
    stage: Optional[str] = None
    expected_value: Optional[float] = None
    probability: Optional[int] = None
    expected_close_date: Optional[str] = None
    owner_id: Optional[UUID] = None
    description: Optional[str] = None


@dataclass
class BizOpportunityOut:
    id: UUID
    client_id: UUID
    name: str
    stage: str = "prospecting"
    code: Optional[str] = None
    expected_value: Optional[float] = None
    probability: Optional[int] = None
    expected_close_date: Optional[str] = None
    owner_id: Optional[UUID] = None
    description: Optional[str] = None
    converted_to_project_id: Optional[UUID] = None
