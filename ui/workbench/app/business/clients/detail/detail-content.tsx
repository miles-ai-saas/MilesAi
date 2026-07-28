"use client";

import { Suspense } from "react";
import { BizDetailPageShell } from "@/features/business/components/BizDetailPageShell";
import { ClientDetailView, useClientDetailPage } from "@/features/clients";

export default function ClientDetailPage({ id }: { id: string }) {
  const vm = useClientDetailPage(id);
  const missingId = !id || id === "_";
  return (
    <Suspense fallback={null}>
      <BizDetailPageShell
        backHref="/business/clients"
        backLabel="返回客户列表"
        loading={!missingId && vm.loading}
        error={missingId ? "缺少客户 ID" : vm.error}
        notFoundLabel="客户不存在"
      >
        {vm.client ? <ClientDetailView vm={vm} /> : null}
      </BizDetailPageShell>
    </Suspense>
  );
}
