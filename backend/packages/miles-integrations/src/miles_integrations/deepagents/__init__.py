"""
DeepAgents 多子智能体编排（可选依赖 ``deepagents`` PyPI 包）。

``AgentService.chat`` 在存在 ``sub_agent_bindings`` 时调用 ``run_subagent_planned_chat``；
未安装包或 ``force_platform_planner`` 时降级为平台 JSON 规划（``orchestrator._run_platform_planned``）。

与本地 KB：子智能体 ``chat_as_child`` 内部仍可走 ``_rag_chat``（绑定知识库时）。
"""

from miles_integrations.deepagents.orchestrator import run_subagent_planned_chat
from miles_integrations.deepagents.runner import deepagents_importable

__all__ = ["deepagents_importable", "run_subagent_planned_chat"]
