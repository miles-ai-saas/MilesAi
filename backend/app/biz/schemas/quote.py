"""商机报价 schemas。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class BizQuoteCreate:
    name: str
    amount: Optional[float] = None
    status: str = "draft"
    version: Optional[str] = None
    valid_until: Optional[str] = None
    remark: Optional[str] = None


@dataclass
class BizQuoteUpdate:
    name: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    version: Optional[str] = None
    valid_until: Optional[str] = None
    remark: Optional[str] = None


@dataclass
class BizQuoteOut:
    id: UUID
    opportunity_id: UUID
    client_id: UUID
    name: str
    amount: Optional[float] = None
    status: str = "draft"
    version: Optional[str] = None
    valid_until: Optional[str] = None
    remark: Optional[str] = None
    created_by: Optional[UUID] = None
