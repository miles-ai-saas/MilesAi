/** 工具工作台：来源标签、时间格式化（枚举文案优先来自 GET /tools/meta）。 */

import type { EnumOption } from "@/lib/enum-meta";
import { optionLabel } from "@/lib/enum-meta";
import type { ToolCatalogItem, ToolsMeta } from "@/lib/types";

export type ToolSourceTab = "" | "builtin" | "custom";

export type ToolPageTab = "catalog" | "logs";

export type ToolKindTab = "http" | "script";

/** 纯 UI Tab，非后端枚举 */
export const TOOL_PAGE_TABS: { key: ToolPageTab; label: string }[] = [
  { key: "catalog", label: "工具列表" },
  { key: "logs", label: "调用日志" },
];

export function catalogSourceTabs(meta?: ToolsMeta | null): { key: ToolSourceTab; label: string }[] {
  const fromApi = meta?.catalog_sources?.map((o) => ({
    key: o.value as ToolSourceTab,
    label: o.label,
  }));
  if (fromApi?.length) return fromApi;
  return [
    { key: "", label: "全部" },
    { key: "builtin", label: "内置" },
    { key: "custom", label: "自定义" },
  ];
}

export function toolKindTabs(meta?: ToolsMeta | null): {
  key: ToolKindTab;
  label: string;
  hint: string;
  available: boolean;
}[] {
  const types = meta?.tool_types;
  if (types?.length) {
    return types.map((o) => ({
      key: o.value as ToolKindTab,
      label: o.label,
      hint: o.hint ?? "",
      available: true,
    }));
  }
  return [
    { key: "http", label: "HTTP", hint: "", available: true },
    { key: "script", label: "脚本", hint: "", available: true },
  ];
}

export function toolKindLabel(kind: string, meta?: ToolsMeta | null): string {
  return optionLabel(meta?.tool_types, kind) || kind;
}

export function toolSourceLabel(source: string, meta?: ToolsMeta | null): string {
  return optionLabel(meta?.catalog_sources, source) || source;
}

export function invocationStatusLabel(status: string, meta?: ToolsMeta | null): string {
  return optionLabel(meta?.invocation_statuses, status) || status;
}

export function formatToolUpdatedAt(item: ToolCatalogItem): string {
  const raw = item.updated_at;
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
