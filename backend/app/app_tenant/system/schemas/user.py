from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6)
    phone: str | None = None
    tenant_id: UUID | None = None
    role_ids: list[UUID] = []


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    is_active: bool | None = None
    role_ids: list[UUID] | None = None


class UserOut(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    phone: str | None
    tenant_id: UUID
    is_active: bool
    is_superuser: bool
    role_codes: list[str] = []

    model_config = {"from_attributes": True}
