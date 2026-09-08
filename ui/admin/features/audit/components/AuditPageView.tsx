"use client";

import { AuditFiltersSection, AuditLogListSection } from "@/features/audit/components/AuditSections";
import { PageHeader } from "@/components/layout/PageHeader";
import type { AuditPageVm } from "@/features/audit/hooks/use-audit-page";
import { AUDIT_PAGE_DESCRIPTION } from "@/features/audit/lib/audit-page-shared";

export function AuditPageView({ vm }: { vm: AuditPageVm }) {
  return (
    <div>
      <PageHeader title="审计日志" description={AUDIT_PAGE_DESCRIPTION} />
      <AuditFiltersSection vm={vm} />
      <AuditLogListSection vm={vm} />
    </div>
  );
}
