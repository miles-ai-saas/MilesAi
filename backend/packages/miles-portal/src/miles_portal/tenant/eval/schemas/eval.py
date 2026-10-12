"""Eval API 请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvalDatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class EvalDatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class EvalDatasetOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    created_at: datetime
    case_count: int = 0

    model_config = {"from_attributes": True}


class EvalCaseCreate(BaseModel):
    query: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=128)
    expected: dict | None = None
    sort_index: int = 0


class EvalCaseUpdate(BaseModel):
    query: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, max_length=128)
    expected: dict | None = None
    sort_index: int | None = None


class EvalCasePromoteFromCallCreate(BaseModel):
    """从智能体调用记录升格用例（成功 / 失败均可）。"""

    agent_id: UUID
    call_id: UUID
    name: str | None = Field(default=None, max_length=128)
    expected: dict | None = None
    prefer_session_text: bool = Field(
        default=True,
        description="优先从会话消息取全文；否则用调用记录 preview",
    )


class EvalCaseCsvImport(BaseModel):
    """CSV 文本导入用例。"""

    csv_text: str = Field(min_length=1, description="含表头的 CSV 文本")


class EvalCaseOut(BaseModel):
    id: UUID
    dataset_id: UUID
    name: str | None
    query: str
    expected: dict | None
    sort_index: int
    created_at: datetime

    model_config = {"from_attributes": True}


class EvalCaseImportResult(BaseModel):
    created: int
    items: list[EvalCaseOut] = Field(default_factory=list)


class EvalRunCreate(BaseModel):
    dataset_id: UUID
    agent_id: UUID
    scoring_mode: str = Field(default="auto", pattern="^(auto|rules|llm_judge)$")
    judge_model_config_id: UUID | None = Field(
        default=None,
        description="LLM Judge 所用模型；空则回退智能体绑定模型",
    )


class EvalRunOut(BaseModel):
    id: UUID
    tenant_id: UUID
    dataset_id: UUID
    agent_id: UUID
    status: str
    scoring_mode: str
    options: dict = Field(default_factory=dict)
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    summary: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class EvalRunItemOut(BaseModel):
    id: UUID
    run_id: UUID
    case_id: UUID
    status: str
    answer_preview: str
    score: float | None
    passed: bool | None
    latency_ms: int
    call_id: UUID | None
    trace_id: str | None
    error_message: str | None
    score_detail: dict
    created_at: datetime

    model_config = {"from_attributes": True}
