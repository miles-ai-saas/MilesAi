/**
 * A2A展示文案：优先 GET /a2a/peers/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。；链路 §4 见 lib/chains.ts。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { A2aMeta } from "@/lib/types";

const PEER_STATUS_FALLBACK: Record<string, string> = {
  pending: "待同步",
  active: "已连通",
  error: "异常",
  inactive: "已停用",
};

const INVOKE_POLICY_FALLBACK: EnumOption[] = [
  { value: "rules_then_plan", label: "规则优先，未命中则自动规划" },
  { value: "rules_only", label: "仅规则触发" },
  { value: "plan_only", label: "仅自动规划" },
];

const ROLE_FALLBACK: EnumOption[] = [
  { value: "retrieval", label: "检索" },
  { value: "ocr", label: "OCR" },
  { value: "summary", label: "总结" },
  { value: "compliance", label: "合规" },
  { value: "custom", label: "自定义" },
];

export function a2aPeerStatusLabel(status: string, meta?: A2aMeta | null): string {
  return optionLabel(meta?.peer_statuses, status) || PEER_STATUS_FALLBACK[status] || status;
}

export function a2aInvokePolicyOptions(meta?: A2aMeta | null): EnumOption[] {
  return meta?.invoke_policies?.length ? meta.invoke_policies : INVOKE_POLICY_FALLBACK;
}

export function a2aPeerRoleHintOptions(meta?: A2aMeta | null): EnumOption[] {
  return meta?.peer_role_hints?.length ? meta.peer_role_hints : ROLE_FALLBACK;
}
