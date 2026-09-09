"""DeepAgents 适配层中性契约（L3，不依赖 tenant 域）。

``ParentChatInput``：父对话输入（L1 ``chat_entry`` 从 ``ChatRequest`` 解包构造）；
``SubAgentPlanResult``：子智能体编排结果（L1 ``chat_entry`` 包回 ``ChatResponse``）。
供 ``orchestrator``/``runner``/``subagent_graphs`` 与 L1 装配点共用。
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
