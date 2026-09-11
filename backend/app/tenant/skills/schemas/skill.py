"""技能包 API 请求/响应模型（Pydantic）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.tags.schemas.tag import TagRefOut


class SkillPackageCreate(BaseModel):
    """遗留创建：可同时写入 tool_names / prompt_snippet 并初始化 SKILL.md。"""

    name: str = Field(..., min_length=1, max_length=128, description="技能包名称")
    description: str | None = Field(default=None, description="技能包描述")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    tag_ids: list[UUID] = Field(default=[], description="标签 ID 列表")
    tool_names: list[str] = Field(default=[], description="关联工具名称列表")
    prompt_snippet: str | None = Field(default=None, description="提示词片段")
    config: dict = Field(default={}, description="扩展配置 JSON")


class SkillPackageCreateBlank(BaseModel):
    """工作台「创建空白技能包」：必填分类，生成默认 frontmatter 的 SKILL.md。"""

    name: str = Field(..., min_length=1, max_length=128, description="技能包名称")
    description: str | None = Field(default=None, description="技能包描述")
    category_id: UUID = Field(description="分类 ID")
    tag_ids: list[UUID] = Field(default=[], description="标签 ID 列表")


class SkillPackageUpdate(BaseModel):
    """元数据 PATCH；文件内容请走 PUT /{id}/file。"""

    name: str | None = Field(default=None, description="技能包名称")
    description: str | None = Field(default=None, description="技能包描述")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    tag_ids: list[UUID] | None = Field(default=None, description="标签 ID 列表（全量替换）")
    tool_names: list[str] | None = Field(default=None, description="关联工具名称列表")
    prompt_snippet: str | None = Field(default=None, description="提示词片段")
    config: dict | None = Field(default=None, description="扩展配置 JSON")
    is_active: bool | None = Field(default=None, description="是否启用")


class SkillPackageOut(BaseModel):
    """列表/详情；category_name 由 SkillService._to_out 填充。"""

    id: UUID = Field(description="技能包 ID")
    tenant_id: UUID = Field(description="租户 ID")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    category_name: str | None = Field(default=None, description="分类名称")
    tags: list[TagRefOut] = Field(default=[], description="标签列表")
    slug: str = Field(description="技能包 slug")
    name: str = Field(description="技能包名称")
    description: str | None = Field(default=None, description="技能包描述")
    source_type: str = Field(description="来源类型")
    tool_names: list[str] = Field(description="关联工具名称列表")
    prompt_snippet: str | None = Field(default=None, description="提示词片段")
    config: dict = Field(description="扩展配置")
    is_active: bool = Field(description="是否启用")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


class SkillFileNode(BaseModel):
    """编辑器左侧文件树节点。"""

    name: str = Field(description="文件或目录名")
    path: str = Field(description="相对技能根的路径")
    type: str = Field(description="节点类型：file | dir")
    children: list["SkillFileNode"] | None = Field(
        default=None,
        description="子节点（目录时）",
    )


# 单个文件的内容（path 为相对技能根路径）。
class SkillFileContent(BaseModel):
    path: str = Field(description="文件相对路径")
    content: str = Field(description="文件内容")


class SkillFileWrite(BaseModel):
    """保存文件；path 为技能根下相对路径（如 SKILL.md）。"""

    path: str = Field(..., min_length=1, max_length=512, description="相对路径")
    content: str = Field(default="", description="文件内容")


# 从本地目录导入技能包的请求。
class SkillImportLocal(BaseModel):
    local_path: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="本地技能目录路径",
    )
    category_id: UUID = Field(description="导入到的分类 ID")
    overwrite_existing: bool = Field(
        default=False,
        description="True=覆盖同名 slug，False=跳过",
    )


# 从 Git 仓库导入技能包的请求。
class SkillImportGit(BaseModel):
    repo_url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Git 仓库 URL",
    )
    category_id: UUID = Field(description="导入到的分类 ID")
    overwrite_existing: bool = Field(
        default=False,
        description="True=覆盖同名 slug，False=跳过",
    )


class SkillImportResult(BaseModel):
    """批量导入统计；errors 为单目录失败原因，不中断整批。"""

    imported: int = Field(default=0, description="成功导入数量")
    skipped: int = Field(default=0, description="跳过数量")
    errors: list[str] = Field(default=[], description="失败原因列表")
