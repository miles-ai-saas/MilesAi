"""交付域 · 项目执行 ORM。"""

import uuid

from sqlalchemy import Date, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.biz.enums import ProjectStatus
from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class BizProject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """项目。

    业务交付的核心单元，聚合合同、工作包、交付物、付款等子实体。
    关联 client 与 opportunity，体现"商机→项目→合同"的转化链路。
    status 按 ProjectStatus 枚举单向流转；total_budget 为项目预算总额，用于成本管控与利润率计算。
    """
    __tablename__ = "biz_projects"
    __table_args__ = (
        Index("idx_biz_projects_tenant", "tenant_id"),
        Index("idx_biz_projects_client", "tenant_id", "client_id"),
        Index("idx_biz_projects_status", "tenant_id", "status"),
        Index("idx_biz_projects_owner", "tenant_id", "owner_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 项目编号，公司内部规则生成，如"PJ-2026-001"
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ProjectStatus.DRAFT.value)
    start_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # 项目经理/负责人
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_budget: Mapped[float | None] = mapped_column(Float, nullable=True)  # 项目预算总额
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # 转化来源商机
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class BizWorkPackage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """工作包。

    项目的执行子单元，按服务线拆分。一个项目可以有多个工作包，每个工作包代表一类服务交付任务。
    stage / stage_index 来自服务线模板的阶段定义，用于按模板流水线推进交付进度。
    status 流转：pending → in_progress → completed。
    budget 与 actual_cost 对比，用于单个工作包的成本偏差分析。
    """
    __tablename__ = "biz_work_packages"
    __table_args__ = (
        Index("idx_biz_wp_tenant", "tenant_id"),
        Index("idx_biz_wp_project", "tenant_id", "project_id"),
        Index("idx_biz_wp_service_line", "tenant_id", "service_line"),
        Index("idx_biz_wp_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    service_line: Mapped[str] = mapped_column(String(64), nullable=False)  # 服务线标识，如"软件开发""咨询""运维"
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 当前所处阶段名称，来源于模板 stages
    stage_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 阶段序号，按模板定义的顺序推进
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending → in_progress → completed
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)  # 工作包预算
    actual_cost: Mapped[float | None] = mapped_column(Float, nullable=True)  # 实际成本，与 budget 对比用于偏差分析
    planned_start: Mapped[str | None] = mapped_column(Date, nullable=True)
    planned_end: Mapped[str | None] = mapped_column(Date, nullable=True)


class BizDeliverable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """交付物。

    项目交付的具体产出，可关联到工作包（work_package_id）或直接归属项目。
    交付物可以是文档、媒体资源或知识库文档，通过 type + attachment_id / media_asset_id / kb_document_id 区分载体。
    status 流转：draft → submitted → accepted，代表草稿→提交→客户验收通过。
    version 用于交付物的版本管理与回溯。
    """
    __tablename__ = "biz_deliverables"
    __table_args__ = (
        Index("idx_biz_deliv_tenant", "tenant_id"),
        Index("idx_biz_deliv_project", "tenant_id", "project_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    work_package_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # 可选，关联具体工作包
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False, default="document")  # document / media / kb_document
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # 类型为 document 时指向附件
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # 类型为 media 时指向媒体资源
    kb_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # 类型为 kb_document 时指向知识库文档
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 版本号，如"v1.0""v2.3"，支持交付物迭代回溯
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")  # draft → submitted → accepted
    submitted_at: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 提交时间，留痕交付节点
    accepted_at: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 验收时间，客户确认的时点
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class BizServiceLineTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """服务线模板。

    定义某类服务（如"软件开发""运维"）的标准交付阶段流水线。
    stages 为 JSONB，存储阶段名称与顺序：如 ["需求分析", "方案设计", "开发", "测试", "上线"]。
    工作包关联 service_line 时自动继承对应模板的阶段定义，is_active 控制模板是否仍在使用。
    tenant_id 为 NULL 表示全局模板（跨租户共享），非 NULL 表示租户自定义模板。
    """
    __tablename__ = "biz_service_line_templates"
    __table_args__ = (
        Index("idx_biz_slt_service_line", "service_line"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # NULL=全局模板, 非NULL=租户自定义
    service_line: Mapped[str] = mapped_column(String(64), nullable=False)  # 服务线标识
    stages: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # 阶段定义，用于驱动工作包的 stage/stage_index
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)  # 是否启用，禁用的模板不再用于新建工作包


class BizProjectMember(Base):
    """项目成员。

    多对多关联表，关联项目与用户。通过复合主键 (project_id, user_id) 去重。
    role_in_project 定义成员在项目中的角色，如 owner / editor / viewer，用于权限控制。
    不继承 UUIDPrimaryKeyMixin 与 TimestampMixin，因为本表以 (project_id, user_id) 为联合主键。
    """
    __tablename__ = "biz_project_members"
    __table_args__ = (
        Index("idx_biz_pm_tenant", "tenant_id"),
        Index("idx_biz_pm_project", "tenant_id", "project_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role_in_project: Mapped[str] = mapped_column(String(64), nullable=False, default="viewer")  # owner / editor / viewer
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
