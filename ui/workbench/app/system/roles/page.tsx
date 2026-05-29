"use client";

/** 角色与权限（链路 §3，壳层 §7）。 */

import { SystemRolesPageView } from "@/components/system-roles/SystemRolesPageView";
import { useSystemRolesPage } from "@/hooks/use-system-roles-page";

export default function SystemRolesPage() {
  const vm = useSystemRolesPage();
  return <SystemRolesPageView vm={vm} />;
}
