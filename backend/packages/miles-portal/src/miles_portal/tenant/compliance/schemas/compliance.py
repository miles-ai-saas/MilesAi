"""合规词库、词条、扫描与拦截日志 schema。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from miles_portal.tenant.compliance.schemas.enums import SensitiveAction

# --- 词库 ---


# 创建敏感词库的入参。
class WordLibraryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="词库名称")
    description: str | None = Field(default=None, description="词库描述")
    is_active: bool = Field(default=True, description="是否启用")
    sort_order: int = Field(default=0, description="排序权重")


# 更新敏感词库；字段均可选，``None`` 表示不修改。
class WordLibraryUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="词库名称",
    )
    description: str | None = Field(default=None, description="词库描述")
    is_active: bool | None = Field(default=None, description="是否启用")
    sort_order: int | None = Field(default=None, description="排序权重")


# 词库输出，附词条数量。
class WordLibraryOut(BaseModel):
    id: UUID = Field(description="词库 ID")
    tenant_id: UUID = Field(description="租户 ID")
    name: str = Field(description="词库名称")
    description: str | None = Field(default=None, description="词库描述")
    is_active: bool = Field(description="是否启用")
    sort_order: int = Field(description="排序权重")
    word_count: int = Field(default=0, description="词条数量")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# --- 库内词条（binding 视图） ---


# 向词库添加单个词条的入参（词面 + 处理策略）。
class LibraryWordCreate(BaseModel):
    word: str = Field(..., min_length=1, max_length=128, description="敏感词文本")
    action: SensitiveAction = Field(
        default=SensitiveAction.WARN,
        description="命中后的处理策略",
    )
    is_active: bool = Field(default=True, description="是否启用")


# 批量为词库添加词条（单次上限 200）。
class LibraryWordBatchCreate(BaseModel):
    words: list[LibraryWordCreate] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="批量添加的词条列表",
    )


# 更新词库内某词条绑定的策略或启用态。
class LibraryWordUpdate(BaseModel):
    action: SensitiveAction | None = Field(default=None, description="处理策略")
    is_active: bool | None = Field(default=None, description="是否启用")


# 库内词条绑定视图输出。
class LibraryWordOut(BaseModel):
    id: UUID = Field(description="库内绑定 ID")
    library_id: UUID = Field(description="词库 ID")
    entry_id: UUID = Field(description="词条 ID")
    word: str = Field(description="敏感词文本")
    action: SensitiveAction = Field(description="处理策略")
    is_active: bool = Field(description="是否启用")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# --- 词条（租户级） ---


# 租户级词条输出，附其所属词库及绑定信息。
class SensitiveWordEntryOut(BaseModel):
    id: UUID = Field(description="词条 ID")
    tenant_id: UUID = Field(description="租户 ID")
    word: str = Field(description="敏感词文本")
    libraries: list["EntryLibraryRef"] = Field(
        default_factory=list,
        description="所属词库及绑定信息",
    )
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# 词条所属词库引用，以及该词在此库内的绑定策略。
class EntryLibraryRef(BaseModel):
    library_id: UUID = Field(description="词库 ID")
    library_name: str = Field(description="词库名称")
    binding_id: UUID = Field(description="绑定 ID")
    action: SensitiveAction = Field(description="在该词库中的处理策略")
    is_active: bool = Field(description="在该词库中是否启用")


# 整体设置词条关联的词库集合（差量增删）。
class EntryLibrariesUpdate(BaseModel):
    library_ids: list[UUID] = Field(
        default_factory=list,
        description="关联的词库 ID 列表",
    )
    default_action: SensitiveAction = Field(
        default=SensitiveAction.WARN,
        description="新建绑定时的默认处理策略",
    )


# --- 租户扫描绑定 ---


# 租户参与合规扫描的词库绑定输出。
class ComplianceScanBindingsOut(BaseModel):
    library_ids: list[UUID] = Field(
        default_factory=list,
        description="参与扫描的词库 ID 列表",
    )
    libraries: list[WordLibraryOut] = Field(
        default_factory=list,
        description="参与扫描的词库详情",
    )


# 设置参与扫描的词库集合。
class ComplianceScanBindingsUpdate(BaseModel):
    library_ids: list[UUID] = Field(
        default_factory=list,
        description="参与扫描的词库 ID 列表",
    )


# --- 扫描 / 日志 ---


# 手动/联调触发的文本扫描入参。
class ComplianceScanRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待扫描文本")
    module: str = Field(default="manual_test", description="扫描来源模块标识")


# 单条命中结果（敏感词及其处理策略）。
class ComplianceScanMatch(BaseModel):
    word: str = Field(description="命中的敏感词")
    action: SensitiveAction = Field(description="该词的处理策略")


# 扫描聚合结果：拦截/警告判定与命中列表。
class ComplianceScanResult(BaseModel):
    blocked: bool = Field(description="是否应拦截")
    warned: bool = Field(description="是否应警告")
    matches: list[ComplianceScanMatch] = Field(description="命中列表")
    scanning_enabled: bool = Field(default=True, description="租户是否启用扫描")


# 拦截日志输出。
class InterceptLogOut(BaseModel):
    id: UUID = Field(description="拦截日志 ID")
    tenant_id: UUID = Field(description="租户 ID")
    user_id: UUID | None = Field(default=None, description="触发用户 ID")
    module: str = Field(description="来源模块")
    direction: str = Field(description="内容方向（入站/出站等）")
    matched_word: str | None = Field(default=None, description="命中的敏感词")
    action: SensitiveAction = Field(description="执行的处理策略")
    content_snippet: str | None = Field(default=None, description="内容摘要")
    created_at: datetime = Field(description="记录时间")

    model_config = {"from_attributes": True}
