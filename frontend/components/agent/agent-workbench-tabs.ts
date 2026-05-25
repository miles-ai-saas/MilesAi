export type AgentWorkbenchTab =
  | "config"
  | "trace"
  | "schedule"
  | "architecture"
  | "api"
  | "logs"
  | "stats";

export const AGENT_WORKBENCH_TABS: {
  id: AgentWorkbenchTab;
  label: string;
  ready: boolean;
}[] = [
  { id: "config", label: "配置", ready: true },
  { id: "trace", label: "Trace", ready: true },
  { id: "schedule", label: "定时", ready: false },
  { id: "architecture", label: "架构", ready: true },
  { id: "api", label: "API", ready: false },
  { id: "logs", label: "日志", ready: false },
  { id: "stats", label: "统计", ready: false },
];

export function isAgentWorkbenchTab(value: string | null): value is AgentWorkbenchTab {
  return AGENT_WORKBENCH_TABS.some((t) => t.id === value);
}
