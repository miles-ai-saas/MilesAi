"""DeepAgents 适配层中性契约（L3，不依赖 tenant 域）。

``ParentChatInput``：父对话输入（L1 ``chat_entry`` 从 ``ChatRequest`` 解包构造）；
``SubAgentPlanResult``：子智能体编排结果（L1 ``chat_entry`` 包回 ``ChatResponse``）；
``AgentServiceLike``：编排所需的最小 L1 服务面（由 ``AgentService`` 结构满足）。
供 ``orchestrator``/``runner``/``subagent_graphs`` 与 L1 装配点共用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from app.models.agent.chat_io import ChatResponse
from app.models.model import ModelConfig


@dataclass
class ParentChatInput:
    """父对话输入的 L3 最小视图：query / inputs / conversation_id。"""

    query: str
    inputs: dict = field(default_factory=dict)
    conversation_id: str | None = None


@dataclass
class SubAgentPlanResult:
    """子智能体编排结果：最终回答与 steps 轨迹（L1 侧转 ``ChatResponse``）。"""

    answer: str
    steps: list[dict] = field(default_factory=list)


class AgentServiceLike(Protocol):
    """deepagents 编排所需的最小 L1 服务面（``AgentService`` 结构满足）。"""

    async def chat_as_child_simple(
        self,
        child_id: UUID,
        *,
        query: str,
        inputs: dict | None = None,
    ) -> ChatResponse:
        """子智能体工位简化入口（内部委托 ``chat_as_child``）。"""
        ...

    async def resolve_system_prompt(self, agent: Any) -> str:
        """合并智能体 system_prompt 与技能/MCP 说明块。"""
        ...

    async def resolve_invoke_model(self, model: ModelConfig | None) -> ModelConfig:
        """按当前租户解析可用模型（合并 BYOK）。"""
        ...

    def chat_usage_sink(self, model: ModelConfig, *, source_id: UUID | None = None) -> Any:
        """构造注入引擎的用量记录器。"""
        ...
