/** 异步任务状态展示文案与样式 */

export const TASK_STATUS_LABEL: Record<string, string> = {
  pending: "等待中",
  running: "运行中",
  success: "成功",
  failed: "失败",
  cancelled: "已取消",
};

export const TASK_STATUS_TABS = [
  { key: "", label: "全部" },
  { key: "pending", label: "等待中" },
  { key: "running", label: "运行中" },
  { key: "failed", label: "失败" },
  { key: "success", label: "成功" },
] as const;

export function taskStatusLabel(status: string): string {
  return TASK_STATUS_LABEL[status] ?? status;
}

export function taskStatusBadgeClass(status: string): string {
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
