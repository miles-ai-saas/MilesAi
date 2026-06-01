"use client";

import Link from "next/link";
import { OpportunitiesTable } from "@/features/opportunities/components/OpportunitiesTable";
import type { OpportunitiesPageVm } from "@/features/opportunities/hooks/use-opportunities-page";

export function OpportunitiesPageView({ vm }: { vm: OpportunitiesPageVm }) {
  const { ready, confirmDialog } = vm;
  if (!ready) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <div className="w-full">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">商机</h1>
          <p className="mt-1 text-sm text-ink-muted">跟踪客户线索、报价与签约全流程</p>
        </div>
        <Link href="/business/opportunities/new" className="btn-primary text-sm">新建商机</Link>
      </div>
      <OpportunitiesTable vm={vm} />
      {confirmDialog}
    </div>
  );
}
