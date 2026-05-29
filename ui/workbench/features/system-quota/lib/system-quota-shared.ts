export const SYSTEM_QUOTA_PAGE_DESC = "查看本租户资源使用与上限。配额调整请联系平台管理员（运营后台）。";

export const SYSTEM_QUOTA_FOOTER_NOTE = "如需提升配额，请联系平台管理员在运营后台调整租户套餐或配额上限。";

export function quotaUsagePct(used: number, max: number) {
  if (max <= 0) return 0;
  return Math.min(100, Math.round((used / max) * 100));
}
