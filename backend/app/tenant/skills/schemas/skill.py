"""技能包 API 请求/响应模型（Pydantic）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.tags.schemas.tag import TagRefOut


class SkillPackageCreate(BaseModel):
    """遗留创建：可同时写入 tool_names / prompt_snippet 并初始化 SKILL.md。"""

    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    category_id: UUID | None = None
    tag_ids: list[UUID] = []
    tool_names: list[str] = []
    prompt_snippet: str | None = None
    config: dict = {}


class SkillPackageCreateBlank(BaseModel):
    """工作台「创建空白技能包」：必填分类，生成默认 frontmatter 的 SKILL.md。"""

    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    category_id: UUID
    tag_ids: list[UUID] = []


class SkillPackageUpdate(BaseModel):
    """元数据 PATCH；文件内容请走 PUT /{id}/file。"""

    name: str | None = None
    description: str | None = None
    category_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    tool_names: list[str] | None = None
    prompt_snippet: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class SkillPackageOut(BaseModel):
    """列表/详情；category_name 由 SkillService._to_out 填充。"""

    id: UUID
    tenant_id: UUID
    category_id: UUID | None
    category_name: str | None = None
    tags: list[TagRefOut] = []
    slug: str
    name: str
    description: str | None
    source_type: str
    tool_names: list[str]
    prompt_snippet: str | None
    config: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SkillFileNode(BaseModel):
    """编辑器左侧文件树节点。"""

    name: str
    path: str
    type: str
    children: list["SkillFileNode"] | None = None


class SkillFileContent(BaseModel):
    path: str
    content: str


class SkillFileWrite(BaseModel):
    """保存文件；path 为技能根下相对路径（如 SKILL.md）。"""

    path: str = Field(..., min_length=1, max_length=512)
    content: str = ""


class SkillImportLocal(BaseModel):
    local_path: str = Field(..., min_length=1, max_length=1024)
    category_id: UUID
    overwrite_existing: bool = False  # True=覆盖同名 slug，False=跳过


class SkillImportGit(BaseModel):
    repo_url: str = Field(..., min_length=1, max_length=2048)
    category_id: UUID
    overwrite_existing: bool = False


class SkillImportResult(BaseModel):
    """批量导入统计；errors 为单目录失败原因，不中断整批。"""

    imported: int = 0
    skipped: int = 0
    errors: list[str] = []
