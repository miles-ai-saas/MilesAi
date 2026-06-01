"""交付物 API schemas。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class BizDeliverableCreate:
    project_id: UUID
    name: str
    type: str = "document"
    work_package_id: Optional[UUID] = None
    attachment_id: Optional[UUID] = None
    media_asset_id: Optional[UUID] = None
    version: Optional[str] = None


@dataclass
class BizDeliverableUpdate:
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    work_package_id: Optional[UUID] = None
    attachment_id: Optional[UUID] = None
    media_asset_id: Optional[UUID] = None
    version: Optional[str] = None


@dataclass
class BizDeliverableOut:
    id: UUID
    project_id: UUID
    name: str
    type: str = "document"
    status: str = "draft"
    work_package_id: Optional[UUID] = None
    attachment_id: Optional[UUID] = None
    media_asset_id: Optional[UUID] = None
    version: Optional[str] = None
    submitted_at: Optional[str] = None
    accepted_at: Optional[str] = None
