"use client";

import { Suspense } from "react";
import { SuppliersPageView, useSuppliersPage } from "@/features/suppliers";

function SuppliersListPageInner() {
  const vm = useSuppliersPage();
  return <SuppliersPageView vm={vm} />;
}

export default function SuppliersListPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">加载中…</p>}>
      <SuppliersListPageInner />
    </Suspense>
  );
}
