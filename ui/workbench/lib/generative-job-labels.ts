/**
 * 生成任务展示文案：GET /generative/jobs/meta（useGenerativeJobMeta）。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";

export type GenerativeJobsMeta = {
  statuses: EnumOption[];
  status_filters: EnumOption[];
  sources: EnumOption[];
  kinds: EnumOption[];
  schema_version: number;
};

const STATUS_FALLBACK: Record<string, string> = {
  pending: "等待中",
  running: "生成中",
  success: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const SOURCE_FALLBACK: Record<string, string> = {
  api: "API",
  agent_tool: "智能体工具",
  flow_node: "流程节点",
};

const FILTER_FALLBACK: EnumOption[] = [
  { value: "", label: "全部" },
  { value: "pending", label: "等待中" },
  { value: "running", label: "生成中" },
  { value: "failed", label: "失败" },
  { value: "success", label: "已完成" },
  { value: "cancelled", label: "已取消" },
];

export function generativeJobStatusLabel(status: string, meta?: GenerativeJobsMeta | null): string {
  return optionLabel(meta?.statuses, status) || STATUS_FALLBACK[status] || status;
}

export function generativeJobSourceLabel(source: string, meta?: GenerativeJobsMeta | null): string {
  return optionLabel(meta?.sources, source) || SOURCE_FALLBACK[source] || source;
}

export function generativeJobStatusFilterOptions(meta?: GenerativeJobsMeta | null): EnumOption[] {
  return meta?.status_filters?.length ? meta.status_filters : FILTER_FALLBACK;
}

export function generativeJobStatusBadgeClass(status: string): string {
  switch (status) {
    case "success":
      return "bg-emerald-50 text-emerald-800 ring-emerald-200";
    case "failed":
      return "bg-red-50 text-red-700 ring-red-200";
    case "running":
      return "bg-amber-50 text-amber-800 ring-amber-200";
    case "pending":
      return "bg-surface-muted text-ink-muted ring-line";
    case "cancelled":
      return "bg-surface-muted text-ink-faint ring-line";
    default:
      return "bg-surface-muted text-ink-muted ring-line";
  }
}

export function canCancelGenerativeJob(status: string): boolean {
  return status === "pending" || status === "running";
}

export function canRetryGenerativeJob(status: string): boolean {
  return status === "failed" || status === "cancelled";
}

export function generativeJobKindLabel(kind: string): string {
  if (kind === "video") return "生视频";
  if (kind === "image") return "生图";
  return kind;
}

export function generativeJobKindFilterOptions(): EnumOption[] {
  return [
    { value: "", label: "全部类型" },
    { value: "image", label: "生图" },
    { value: "video", label: "生视频" },
  ];
}

export function isGenerativeJobTerminal(status: string): boolean {
  return status === "success" || status === "failed" || status === "cancelled";
}
