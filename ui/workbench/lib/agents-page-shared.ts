import type { AgentType } from "@/lib/types";

export type AgentsTab = "all" | "custom" | "a2a";

export const AGENTS_TAB_ITEMS = [
  { key: "all" as const, label: "全部" },
  { key: "custom" as const, label: "智能体" },
  { key: "a2a" as const, label: "A2A 互联" },
];

export const AGENTS_TAB_DESCRIPTIONS: Record<AgentsTab, string> = {
  all: "查看全部平台内智能体（不含 A2A 互联宿主）；A2A 能力请在「A2A 互联」Tab 管理。",
  custom: "配置模型、知识库与工具；可选内部协同，或引用已登记的外部 A2A（规则触发 + 自动规划）。",
  a2a: "管理 A2A 协议能力：先在「外部登记」同步 Agent Card，再创建「互联宿主」作为统一对话入口。",
};

export function agentsTabToApiType(tab: AgentsTab): AgentType | undefined {
  if (tab === "custom") return "custom";
  if (tab === "a2a") return "a2a";
  return undefined;
}
