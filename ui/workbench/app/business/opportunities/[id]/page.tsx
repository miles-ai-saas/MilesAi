"use client";

import { useParams } from "next/navigation";
import { BizDetailPageShell } from "@/features/business/components/BizDetailPageShell";
import { OpportunityDetailView, useOpportunityDetailPage } from "@/features/opportunities";

export default function OpportunityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const vm = useOpportunityDetailPage(id);
  return (
    <BizDetailPageShell
      backHref="/business/opportunities"
      backLabel="返回商机列表"
      loading={vm.loading}
      error={vm.error}
      notFoundLabel="商机不存在"
    >
      {vm.opp ? <OpportunityDetailView vm={vm} /> : null}
    </BizDetailPageShell>
  );
}
