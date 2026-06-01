"""服务线模板市场 schemas。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.biz.schemas.service_line_template import BizServiceLineTemplateOut


@dataclass
class BizServiceLineTemplatePackOut:
    id: str
    service_line: str
    service_line_label: str
    name: str
    description: str | None
    stages: list[str] = field(default_factory=list)
    ai_config: dict = field(default_factory=dict)
    publisher_name: str = "Miles 官方"
    publisher_type: str = "platform"
    publisher_tenant_id: str | None = None
    tags: list[str] = field(default_factory=list)
    is_featured: bool = False
    is_active: bool = True
    install_count: int = 0
    status: str = "published"
    review_note: str | None = None
    submitted_at: str | None = None
    reviewed_at: str | None = None
    is_mine: bool = False


@dataclass
class BizServiceLineTemplatePackApplyResult:
    pack_id: str
    pack_name: str
    service_line: str
    template: BizServiceLineTemplateOut


@dataclass
class BizServiceLineTemplatePackCreate:
    service_line: str
    name: str
    description: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class BizServiceLineTemplatePackUpdate:
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    stages: list[str] | None = None
    ai_config: dict | None = None
