"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { RiskEventsSection } from "@/features/risk/components/RiskEventsSection";
import { RiskIpBlacklistSection } from "@/features/risk/components/RiskIpBlacklistSection";
import { RiskRateLimitEditDialog } from "@/features/risk/components/RiskRateLimitEditDialog";
import { RiskRateLimitSection } from "@/features/risk/components/RiskRateLimitSection";
import type { RiskPageVm } from "@/features/risk/hooks/use-risk-page";
import { RISK_PAGE_DESC } from "@/features/risk/lib/risk-page-shared";

export function RiskPageView({ vm }: { vm: RiskPageVm }) {
  const { ruleMsg, ruleErr } = vm;

  return (
    <>
      <div className="admin-page-stack">
        <PageHeader title="风控管理" description={RISK_PAGE_DESC} />

        {ruleMsg && <p className="admin-alert-ok">{ruleMsg}</p>}
        {ruleErr && <p className="admin-alert-err">{ruleErr}</p>}

        <RiskEventsSection vm={vm} />
        <RiskIpBlacklistSection vm={vm} />
        <RiskRateLimitSection vm={vm} />
      </div>
      <RiskRateLimitEditDialog vm={vm} />
    </>
  );
}
