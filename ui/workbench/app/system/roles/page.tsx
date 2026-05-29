"use client";

/** 角色与权限（链路 §3，壳层 §7）。 */

import { SystemRolesPageView, useSystemRolesPage } from "@/features/system-roles";

export default function SystemRolesPage() {
  const vm = useSystemRolesPage();
  return <SystemRolesPageView vm={vm} />;
}
