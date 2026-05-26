/**
 * 技能包展示文案：优先 GET /skill-packages/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。；链路 §4 见 lib/chains.ts。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { SkillMeta } from "@/lib/types";

const SOURCE_FALLBACK: Record<string, string> = {
  manual: "手动创建",
  local: "本地目录",
  zip: "ZIP",
  git: "Git",
};

const ACTIVE_FALLBACK: Record<string, string> = {
  active: "启用",
  inactive: "停用",
};

export function skillSourceTypeLabel(sourceType: string, meta?: SkillMeta | null): string {
  return optionLabel(meta?.source_types, sourceType) || SOURCE_FALLBACK[sourceType] || sourceType;
}

export function skillActiveLabel(isActive: boolean, meta?: SkillMeta | null): string {
  const key = isActive ? "active" : "inactive";
  return optionLabel(meta?.active_states, key) || ACTIVE_FALLBACK[key];
}
