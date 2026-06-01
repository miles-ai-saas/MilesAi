"use client";

import { Suspense } from "react";
import { OpportunitiesPageView, useOpportunitiesPage } from "@/features/opportunities";

function OpportunitiesListPageInner() {
  const vm = useOpportunitiesPage();
  return <OpportunitiesPageView vm={vm} />;
}

export default function OpportunitiesListPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">加载中…</p>}>
      <OpportunitiesListPageInner />
    </Suspense>
  );
}
