"use client";

import { AuditPageView } from "@/components/audit/AuditPageView";
import { useAuditPage } from "@/hooks/use-audit-page";

export default function AuditPage() {
  const vm = useAuditPage();
  return <AuditPageView vm={vm} />;
}
