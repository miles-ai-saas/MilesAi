"use client";

/** 租户用户管理（链路 §3，壳层 §7 SystemShell）。 */

import { SystemUsersPageView } from "@/components/system-users/SystemUsersPageView";
import { useSystemUsersPage } from "@/hooks/use-system-users-page";

export default function SystemUsersPage() {
  const vm = useSystemUsersPage();
  return <SystemUsersPageView vm={vm} />;
}
