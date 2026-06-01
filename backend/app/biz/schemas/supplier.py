"""供应商 API schemas。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


@dataclass
class BizSupplierCreate:
    name: str
    short_name: Optional[str] = None
    category: str = "other"
    status: str = "active"
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    remark: Optional[str] = None


@dataclass
class BizSupplierUpdate:
    name: Optional[str] = None
    short_name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    remark: Optional[str] = None


@dataclass
class BizSupplierContactCreate:
    name: str
    title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False


@dataclass
class BizSupplierContactOut:
    id: UUID
    supplier_id: UUID
    name: str
    title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False


@dataclass
class BizSupplierOut:
    id: UUID
    name: str
    category: str
    status: str
    short_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    remark: Optional[str] = None
    project_count: int = 0
    contacts: list[BizSupplierContactOut] = field(default_factory=list)


@dataclass
class BizProjectSupplierCreate:
    supplier_id: UUID
    work_package_id: Optional[UUID] = None
    role_description: Optional[str] = None
    contracted_amount: Optional[float] = None
    status: str = "active"
    remark: Optional[str] = None


@dataclass
class BizProjectSupplierUpdate:
    work_package_id: Optional[UUID] = None
    role_description: Optional[str] = None
    contracted_amount: Optional[float] = None
    status: Optional[str] = None
    remark: Optional[str] = None


@dataclass
class BizProjectSupplierOut:
    project_id: UUID
    supplier_id: UUID
    supplier_name: str
    supplier_category: str
    work_package_id: Optional[UUID] = None
    role_description: Optional[str] = None
    contracted_amount: Optional[float] = None
    status: str = "active"
    remark: Optional[str] = None
