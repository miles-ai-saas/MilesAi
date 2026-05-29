export const SYSTEM_SESSIONS_PAGE_DESC = "查看当前账号在各设备上的活跃登录，可强制下线可疑会话。";

export function formatSessionTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN");
}
