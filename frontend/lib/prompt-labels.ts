/**
 * 提示词展示文案：优先 GET /prompt-templates/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。
 */

import { optionLabel } from "@/lib/enum-meta";
import type { PromptMeta } from "@/lib/types";

export function promptActiveLabel(isActive: boolean, meta?: PromptMeta | null): string {
  const key = isActive ? "active" : "inactive";
  return optionLabel(meta?.active_states, key) || (isActive ? "启用" : "停用");
}
