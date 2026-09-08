"use client";

export default function AuditPage() {
  const vm = useAuditPage();
  return <AuditPageView vm={vm} />;
}
import { AuditPageView, useAuditPage } from "@/features/audit";
