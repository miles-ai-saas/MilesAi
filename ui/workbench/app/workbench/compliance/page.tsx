"use client";

/** 合规词库（链路 §13）：词库/日志/试扫 + `useComplianceMeta`。 */

import { Suspense } from "react";
import { CompliancePageView } from "@/components/compliance/CompliancePageView";
import { useCompliancePage } from "@/hooks/use-compliance-page";

function CompliancePageContent() {
  const vm = useCompliancePage();
  return <CompliancePageView vm={vm} />;
}

export default function CompliancePage() {
  return (
    <Suspense fallback={<div className="flex min-h-[40vh] items-center justify-center text-sm text-ink-muted">加载合规页面…</div>}>
      <CompliancePageContent />
    </Suspense>
  );
}
