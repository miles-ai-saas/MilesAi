/** 审计日志页共享常量与纯函数。 */

export const SYSTEM_AUDIT_PAGE_DESC = "记录租户内关键操作行为。";

export function formatAuditTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN");
}

export function shortenId(id: string, head = 8): string {
  if (id.length <= head + 1) return id;
  return `${id.slice(0, head)}…`;
}
