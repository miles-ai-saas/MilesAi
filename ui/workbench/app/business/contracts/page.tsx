"use client";

import { Suspense } from "react";
import { ContractsPageView, useContractsPage } from "@/features/contracts";

function ContractsListPageInner() {
  const vm = useContractsPage();
  return <ContractsPageView vm={vm} />;
}

export default function ContractsListPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">加载中…</p>}>
      <ContractsListPageInner />
    </Suspense>
  );
}
