/**
 * 标签 entity_type展示文案：优先 GET /tags/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。；链路 §4 见 lib/chains.ts。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { TagMeta } from "@/lib/types";

const ENTITY_FALLBACK: Record<string, string> = {
  agent: "智能体",
  prompt: "提示词",
  skill: "技能包",
  tool: "工具",
  flow: "流程",
};

export function tagEntityTypeLabel(entityType: string, meta?: TagMeta | null): string {
  return optionLabel(meta?.entity_types, entityType) || ENTITY_FALLBACK[entityType] || entityType;
}

export function tagEntityTypeOptions(meta?: TagMeta | null): EnumOption[] {
  if (meta?.entity_types?.length) return meta.entity_types;
  return Object.entries(ENTITY_FALLBACK).map(([value, label]) => ({ value, label }));
}
