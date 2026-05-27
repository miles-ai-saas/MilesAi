/** 对话工作台右侧 Tab 键（链路 §5，纯 UI 枚举）。 */

export type AgentWorkbenchTab =
  | "config"
  | "trace"
  | "schedule"
  | "architecture"
  | "api"
  | "call_records"
  | "stats";

export const AGENT_WORKBENCH_TABS: {
  id: AgentWorkbenchTab;
  label: string;
  ready: boolean;
}[] = [
  { id: "config", label: "配置", ready: true },
  { id: "trace", label: "Trace", ready: true },
  { id: "schedule", label: "定时", ready: true },
  { id: "architecture", label: "架构", ready: true },
  { id: "api", label: "API", ready: false },
  { id: "call_records", label: "调用记录", ready: false },
  { id: "stats", label: "统计", ready: true },
];

export function normalizeAgentWorkbenchTab(value: string | null): AgentWorkbenchTab | null {
  if (!value) return null;
  return AGENT_WORKBENCH_TABS.some((t) => t.id === value) ? (value as AgentWorkbenchTab) : null;
}

export function isAgentWorkbenchTab(value: string | null): value is AgentWorkbenchTab {
  return normalizeAgentWorkbenchTab(value) != null;
}
