/**
 * 合规展示文案：优先 GET /compliance/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。；链路 §4 见 lib/chains.ts。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { ComplianceMeta } from "@/lib/types";

export function sensitiveActionLabel(
  action: string,
  meta?: ComplianceMeta | null,
  actions?: EnumOption[],
): string {
  return optionLabel(actions ?? meta?.sensitive_actions, action) || action;
}
