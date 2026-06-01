"""合同 API schemas。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class BizContractCreate:
    project_id: UUID
    client_id: UUID
    name: str
    contract_no: Optional[str] = None
    type: str = "service"
    signed_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_amount: Optional[float] = None
    payment_terms: Optional[str] = None
    description: Optional[str] = None


@dataclass
class BizContractUpdate:
    name: Optional[str] = None
    contract_no: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    signed_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_amount: Optional[float] = None
    payment_terms: Optional[str] = None
    description: Optional[str] = None


@dataclass
class BizContractOut:
    id: UUID
    project_id: UUID
    client_id: UUID
    name: str
    status: str = "draft"
    type: str = "service"
    contract_no: Optional[str] = None
    signed_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_amount: Optional[float] = None
    payment_terms: Optional[str] = None
    description: Optional[str] = None
