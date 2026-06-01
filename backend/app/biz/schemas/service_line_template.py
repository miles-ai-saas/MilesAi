"""服务线阶段模板 schemas。"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class BizServiceLineTemplateOut:
    service_line: str
    label: str
    stages: list[str] = field(default_factory=list)
    source: str = "none"  # global | tenant | none
    template_id: str | None = None
    is_active: bool = True
    is_editable: bool = False


@dataclass
class BizServiceLineTemplateUpsert:
    stages: list[str]
    is_active: bool = True
