"""收付款 API schemas。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class BizPaymentCreate:
    contract_id: UUID
    project_id: UUID
    name: str
    direction: str = "in"
    amount: float = 0
    planned_date: Optional[str] = None
    method: Optional[str] = None
    remark: Optional[str] = None


@dataclass
class BizPaymentUpdate:
    name: Optional[str] = None
    direction: Optional[str] = None
    amount: Optional[float] = None
    planned_date: Optional[str] = None
    paid_date: Optional[str] = None
    method: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None


@dataclass
class BizPaymentOut:
    id: UUID
    contract_id: UUID
    project_id: UUID
    name: str
    direction: str = "in"
    amount: float = 0
    status: str = "pending"
    planned_date: Optional[str] = None
    paid_date: Optional[str] = None
    method: Optional[str] = None
    remark: Optional[str] = None


@dataclass
class FinancialSummaryOut:
    total_income: float = 0
    total_paid: float = 0
    total_pending_in: float = 0
    total_pending_out: float = 0
    contract_count: int = 0
