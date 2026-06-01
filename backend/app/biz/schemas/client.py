"""客户 API schemas。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


@dataclass
class BizClientCreate:
    name: str
    short_name: Optional[str] = None
    industry: Optional[str] = None
    confidentiality_level: str = "normal"
    address: Optional[str] = None
    remark: Optional[str] = None


@dataclass
class BizClientUpdate:
    name: Optional[str] = None
    short_name: Optional[str] = None
    industry: Optional[str] = None
    confidentiality_level: Optional[str] = None
    address: Optional[str] = None
    remark: Optional[str] = None


@dataclass
class BizClientContactCreate:
    name: str
    title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False


@dataclass
class BizClientContactOut:
    id: UUID
    client_id: UUID
    name: str
    title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False


@dataclass
class BizClientOut:
    id: UUID
    name: str
    confidentiality_level: str
    short_name: Optional[str] = None
    industry: Optional[str] = None
    address: Optional[str] = None
    remark: Optional[str] = None
    project_count: int = 0
    contacts: list[BizClientContactOut] = field(default_factory=list)
