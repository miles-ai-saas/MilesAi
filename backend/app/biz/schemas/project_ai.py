"""项目 AI 上下文 schemas。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


@dataclass
class BizServiceLineAiRecommendation:
    service_line: str
    service_line_label: str
    work_package_id: Optional[UUID] = None
    work_package_name: Optional[str] = None
    stage: Optional[str] = None
    agent_tag: Optional[str] = None
    recommended_agent_id: Optional[UUID] = None
    recommended_agent_name: Optional[str] = None
    flow_template_id: Optional[str] = None
    flow_template_label: Optional[str] = None
    chat_hint: Optional[str] = None
    quick_prompts: list[str] = field(default_factory=list)


@dataclass
class BizRelatedCaseOut:
    kb_id: UUID
    kb_name: str
    document_id: UUID
    document_title: str
    project_id: UUID
    project_name: str
    service_line: str | None = None
    deliverable_name: str = ""


@dataclass
class BizProjectAiContextOut:
    project_id: UUID
    project_name: str
    client_id: UUID
    client_name: str
    confidentiality_level: str
    rag_enabled: bool
    project_status: str
    context_text: str
    retrospective_available: bool = False
    retrospective_prompt: Optional[str] = None
    recommendations: list[BizServiceLineAiRecommendation] = field(default_factory=list)
    related_cases: list[BizRelatedCaseOut] = field(default_factory=list)
