"use client";

/** 租户用户管理（链路 §3，壳层 §7 SystemShell）。 */

import { SystemUsersPageView, useSystemUsersPage } from "@/features/system-users";

export default function SystemUsersPage() {
  const vm = useSystemUsersPage();
  return <SystemUsersPageView vm={vm} />;
}
