"use client";

import Link from "next/link";
import { ContractsTable } from "@/features/contracts/components/ContractsTable";
import type { ContractsPageVm } from "@/features/contracts/hooks/use-contracts-page";

export function ContractsPageView({ vm }: { vm: ContractsPageVm }) {
  const { ready, confirmDialog } = vm;
  if (!ready) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <div className="w-full">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">合同</h1>
          <p className="mt-1 text-sm text-ink-muted">管理项目合同签署、履约与收付款</p>
        </div>
        <Link href="/business/contracts/new" className="btn-primary text-sm">新建合同</Link>
      </div>
      <ContractsTable vm={vm} />
      {confirmDialog}
    </div>
  );
}
