/** 租户 RBAC 权限判断（系统管理导航与按钮）。 */

import type { UserInfo } from "./types";

export function hasPermission(user: UserInfo | null | undefined, code: string): boolean {
  if (!user) return false;
  if (user.is_superuser || user.permissions.includes("*")) return true;
  return user.permissions.includes(code);
}

export function hasAnyPermission(
  user: UserInfo | null | undefined,
  codes: string[],
): boolean {
  return codes.some((c) => hasPermission(user, c));
}
