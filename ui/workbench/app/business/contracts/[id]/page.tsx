"use client";

import { useParams } from "next/navigation";
import { BizDetailPageShell } from "@/features/business/components/BizDetailPageShell";
import { ContractDetailView, useContractDetailPage } from "@/features/contracts";

export default function ContractDetailPage() {
  const { id } = useParams<{ id: string }>();
  const vm = useContractDetailPage(id);
  return (
    <BizDetailPageShell
      backHref="/business/contracts"
      backLabel="返回合同列表"
      loading={vm.loading}
      error={vm.error}
      notFoundLabel="合同不存在"
    >
      {vm.contract ? <ContractDetailView vm={vm} /> : null}
    </BizDetailPageShell>
  );
}
