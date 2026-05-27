/** 与 backend `tenant/agents/constants.py` 及 GET /agents/meta 对齐。 */

export const AGENT_RUNTIME_MODE = {
  LEGACY: "legacy",
  AUTONOMOUS: "autonomous",
  WORKFLOW: "workflow",
} as const;

export type AgentRuntimeMode =
  (typeof AGENT_RUNTIME_MODE)[keyof typeof AGENT_RUNTIME_MODE];

export const AGENT_PLANNER = {
  DEEPAGENTS: "deepagents",
  PLATFORM: "platform",
  A2A_ORCHESTRATOR: "a2a_orchestrator",
} as const;

export type AgentPlanner = (typeof AGENT_PLANNER)[keyof typeof AGENT_PLANNER];
