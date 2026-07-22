"use client";

import { Suspense } from "react";
import { BizDetailPageShell } from "@/features/business/components/BizDetailPageShell";
import { SupplierDetailView, useSupplierDetailPage } from "@/features/suppliers";

export default function SupplierDetailPage({ id }: { id: string }) {
  const vm = useSupplierDetailPage(id);
  return (
    <Suspense fallback={null}>
      <BizDetailPageShell
        backHref="/business/suppliers"
        backLabel="返回供应商列表"
        loading={vm.loading}
        error={vm.error}
        notFoundLabel="供应商不存在"
      >
        {vm.supplier ? <SupplierDetailView vm={vm} /> : null}
      </BizDetailPageShell>
    </Suspense>
  );
}
