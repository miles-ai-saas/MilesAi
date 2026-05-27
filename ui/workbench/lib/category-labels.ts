/**
 * 分类 domain 展示文案：优先 GET /categories/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。；链路 §4 见 lib/chains.ts。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { CategoryDomain, CategoryMeta } from "@/lib/types";

const DOMAIN_FALLBACK: Record<CategoryDomain, string> = {
  agent: "智能体",
  prompt: "提示词",
  skill: "技能包",
  tool: "工具",
};

export function categoryDomainLabel(domain: CategoryDomain, meta?: CategoryMeta | null): string {
  return optionLabel(meta?.domains, domain) || DOMAIN_FALLBACK[domain] || domain;
}

export function categoryDomainOptions(meta?: CategoryMeta | null): EnumOption[] {
  if (meta?.domains?.length) return meta.domains;
  return (Object.keys(DOMAIN_FALLBACK) as CategoryDomain[]).map((value) => ({
    value,
    label: DOMAIN_FALLBACK[value],
  }));
}
