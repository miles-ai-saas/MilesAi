"use client";

import { ComplianceLogsTab } from "@/features/compliance/components/ComplianceLogsTab";
import { ComplianceTestTab } from "@/features/compliance/components/ComplianceTestTab";
import { ComplianceWordsTab } from "@/features/compliance/components/ComplianceWordsTab";
import type { CompliancePageVm } from "@/features/compliance/hooks/use-compliance-page";

export function CompliancePageView({ vm }: { vm: CompliancePageVm }) {
  if (vm.tab === "logs") return <ComplianceLogsTab vm={vm} />;
  if (vm.tab === "test") return <ComplianceTestTab vm={vm} />;
  return <ComplianceWordsTab vm={vm} />;
}
