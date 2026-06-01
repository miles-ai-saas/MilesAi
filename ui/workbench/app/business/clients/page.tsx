"use client";

import { Suspense } from "react";
import { ClientsPageView, useClientsPage } from "@/features/clients";

function ClientsListPageInner() {
  const vm = useClientsPage();
  return <ClientsPageView vm={vm} />;
}

export default function ClientsListPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">加载中…</p>}>
      <ClientsListPageInner />
    </Suspense>
  );
}
