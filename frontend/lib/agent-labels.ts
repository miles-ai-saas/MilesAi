/**
 * 智能体展示文案：优先 GET /agents/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { Agent, AgentMeta } from "@/lib/types";

const STATUS_FALLBACK: Record<string, string> = {
  enabled: "启用",
  disabled: "禁用",
};

const TYPE_FALLBACK: Record<string, string> = {
  custom: "平台内",
  a2a: "A2A 互联宿主",
};

const ROLE_FALLBACK: EnumOption[] = [
  { value: "", label: "未指定" },
  { value: "retrieval", label: "检索" },
  { value: "ocr", label: "OCR" },
  { value: "summary", label: "总结" },
  { value: "compliance", label: "合规" },
  { value: "custom", label: "自定义" },
];

export function agentStatusLabel(status: string, meta?: AgentMeta | null): string {
  return optionLabel(meta?.statuses, status) || STATUS_FALLBACK[status] || status;
}

export function agentTypeLabel(agent: Agent, meta?: AgentMeta | null): string {
  const t = agent.agent_type ?? "custom";
  return optionLabel(meta?.agent_types, t) || TYPE_FALLBACK[t] || t;
}

export function subAgentRoleLabel(roleHint?: string | null, meta?: AgentMeta | null): string {
  const value = roleHint ?? "";
  return optionLabel(meta?.sub_agent_role_hints, value) || optionLabel(ROLE_FALLBACK, value) || value || "未指定";
}

export function subAgentRoleOptions(meta?: AgentMeta | null): EnumOption[] {
  return meta?.sub_agent_role_hints?.length ? meta.sub_agent_role_hints : ROLE_FALLBACK;
}
