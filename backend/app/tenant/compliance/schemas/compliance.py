from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.compliance.models import SensitiveAction


# --- 词库 ---


class WordLibraryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    is_active: bool = True
    sort_order: int = 0


class WordLibraryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class WordLibraryOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    is_active: bool
    sort_order: int
    word_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# --- 库内词条（binding 视图） ---


class LibraryWordCreate(BaseModel):
    word: str = Field(..., min_length=1, max_length=128)
    action: SensitiveAction = SensitiveAction.WARN
    is_active: bool = True


class LibraryWordBatchCreate(BaseModel):
    words: list[LibraryWordCreate] = Field(..., min_length=1, max_length=200)


class LibraryWordUpdate(BaseModel):
    action: SensitiveAction | None = None
    is_active: bool | None = None


class LibraryWordOut(BaseModel):
    id: UUID
    library_id: UUID
    entry_id: UUID
    word: str
    action: SensitiveAction
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- 词条（租户级） ---


class SensitiveWordEntryOut(BaseModel):
    id: UUID
    tenant_id: UUID
    word: str
    libraries: list["EntryLibraryRef"] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class EntryLibraryRef(BaseModel):
    library_id: UUID
    library_name: str
    binding_id: UUID
    action: SensitiveAction
    is_active: bool


class EntryLibrariesUpdate(BaseModel):
    library_ids: list[UUID] = Field(default_factory=list)
    default_action: SensitiveAction = SensitiveAction.WARN


# --- 租户扫描绑定 ---


class ComplianceScanBindingsOut(BaseModel):
    library_ids: list[UUID] = Field(default_factory=list)
    libraries: list[WordLibraryOut] = Field(default_factory=list)


class ComplianceScanBindingsUpdate(BaseModel):
    library_ids: list[UUID] = Field(default_factory=list)


# --- 扫描 / 日志 ---


class ComplianceScanRequest(BaseModel):
    text: str = Field(..., min_length=1)
    module: str = "manual_test"


class ComplianceScanMatch(BaseModel):
    word: str
    action: SensitiveAction


class ComplianceScanResult(BaseModel):
    blocked: bool
    warned: bool
    matches: list[ComplianceScanMatch]
    scanning_enabled: bool = True


class InterceptLogOut(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID | None
    module: str
    direction: str
    matched_word: str | None
    action: SensitiveAction
    content_snippet: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
