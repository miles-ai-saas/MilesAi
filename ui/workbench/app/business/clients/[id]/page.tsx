"use client";

import { useParams } from "next/navigation";
import { BizDetailPageShell } from "@/features/business/components/BizDetailPageShell";
import { ClientDetailView, useClientDetailPage } from "@/features/clients";

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const vm = useClientDetailPage(id);
  return (
    <BizDetailPageShell
      backHref="/business/clients"
      backLabel="返回客户列表"
      loading={vm.loading}
      error={vm.error}
      notFoundLabel="客户不存在"
    >
      {vm.client ? <ClientDetailView vm={vm} /> : null}
    </BizDetailPageShell>
  );
}
