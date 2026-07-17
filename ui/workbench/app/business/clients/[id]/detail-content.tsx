"use client";

import { Suspense } from "react";
import { BizDetailPageShell } from "@/features/business/components/BizDetailPageShell";
import { ClientDetailView, useClientDetailPage } from "@/features/clients";

export default function ClientDetailPage({ id }: { id: string }) {
  const vm = useClientDetailPage(id);
  if (!vm.client) return null;
  return (
    <Suspense fallback={null}>
      <BizDetailPageShell
        backHref="/business/clients"
        backLabel="返回客户列表"
        loading={vm.loading}
        error={vm.error}
        notFoundLabel="客户不存在"
      >
        <ClientDetailView vm={vm} />
      </BizDetailPageShell>
    </Suspense>
  );
}
