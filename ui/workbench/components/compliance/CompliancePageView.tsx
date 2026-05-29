"use client";

import { ComplianceLogsTab } from "@/components/compliance/ComplianceLogsTab";
import { ComplianceTestTab } from "@/components/compliance/ComplianceTestTab";
import { ComplianceWordsTab } from "@/components/compliance/ComplianceWordsTab";
import type { CompliancePageVm } from "@/hooks/use-compliance-page";

export function CompliancePageView({ vm }: { vm: CompliancePageVm }) {
  if (vm.tab === "logs") return <ComplianceLogsTab vm={vm} />;
  if (vm.tab === "test") return <ComplianceTestTab vm={vm} />;
  return <ComplianceWordsTab vm={vm} />;
}
