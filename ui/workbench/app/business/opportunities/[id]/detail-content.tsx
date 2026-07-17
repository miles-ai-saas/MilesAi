"use client";

import { Suspense } from "react";
import { BizDetailPageShell } from "@/features/business/components/BizDetailPageShell";
import { OpportunityDetailView, useOpportunityDetailPage } from "@/features/opportunities";

export default function OpportunityDetailPage({ id }: { id: string }) {
  const vm = useOpportunityDetailPage(id);
  return (
    <Suspense fallback={null}>
      <BizDetailPageShell
        backHref="/business/opportunities"
        backLabel="返回商机列表"
        loading={vm.loading}
        error={vm.error}
        notFoundLabel="商机不存在"
      >
        {vm.opp ? <OpportunityDetailView vm={vm} /> : null}
      </BizDetailPageShell>
    </Suspense>
  );
}
