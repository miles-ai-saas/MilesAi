"use client";

/** 审计日志（链路 §3 + §4 `useAuditMeta`，壳层 §7）。 */

import { SystemAuditPageView } from "@/components/system-audit/SystemAuditPageView";
import { useSystemAuditPage } from "@/hooks/use-system-audit-page";

export default function SystemAuditPage() {
  const vm = useSystemAuditPage();
  return <SystemAuditPageView vm={vm} />;
}
