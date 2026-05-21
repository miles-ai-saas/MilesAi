from uuid import UUID

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminInfo(BaseModel):
    id: UUID
    username: str
    email: str | None
    display_name: str | None
    role: str

    model_config = {"from_attributes": True}


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


class AdminSessionOut(BaseModel):
    admin_id: UUID
    username: str
    role: str
    jti: str | None = None
