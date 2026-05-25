/** 工具工作台：来源标签、时间格式化。 */

import type { ToolCatalogItem } from "@/lib/types";

export type ToolSourceTab = "" | "builtin" | "custom";

export const TOOL_SOURCE_TABS: { key: ToolSourceTab; label: string }[] = [
  { key: "", label: "全部" },
  { key: "builtin", label: "内置" },
  { key: "custom", label: "自定义" },
];

export type ToolPageTab = "catalog" | "logs";

export const TOOL_PAGE_TABS: { key: ToolPageTab; label: string }[] = [
  { key: "catalog", label: "工具列表" },
  { key: "logs", label: "调用日志" },
];

export type ToolKindTab = "http" | "script";

export const TOOL_KIND_TABS: { key: ToolKindTab; label: string; hint: string; available: boolean }[] = [
  {
    key: "http",
    label: "HTTP",
    hint: "调用 REST API，支持 URL 模板与参数映射",
    available: true,
  },
  {
    key: "script",
    label: "Python 脚本",
    hint: "在 MCP Runner 沙箱内运行，须定义 run(params) 函数",
    available: true,
  },
];

export function toolKindLabel(kind: string): string {
  if (kind === "http") return "HTTP";
  if (kind === "script") return "脚本";
  return kind;
}

export function toolSourceLabel(source: string): string {
  if (source === "builtin") return "内置";
  if (source === "custom") return "自定义";
  return source;
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
