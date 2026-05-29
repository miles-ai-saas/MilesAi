"use client";

/** 审计日志（链路 §3 + §4 `useAuditMeta`，壳层 §7）。 */

import { SystemAuditPageView, useSystemAuditPage } from "@/features/system-audit";

export default function SystemAuditPage() {
  const vm = useSystemAuditPage();
  return <SystemAuditPageView vm={vm} />;
}
