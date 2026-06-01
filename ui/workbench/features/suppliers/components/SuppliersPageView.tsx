"use client";

import Link from "next/link";
import { SuppliersFilters, SuppliersTable } from "@/features/suppliers/components/SuppliersTable";
import type { SuppliersPageVm } from "@/features/suppliers/hooks/use-suppliers-page";

export function SuppliersPageView({ vm }: { vm: SuppliersPageVm }) {
  const { ready, confirmDialog } = vm;

  if (!ready) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <div className="w-full">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">供应商</h1>
          <p className="mt-1 text-sm text-ink-muted">管理印刷、拍摄、搭建、场务等外包合作方</p>
        </div>
        <Link href="/business/suppliers/new" className="btn-primary text-sm">新建供应商</Link>
      </div>
      <SuppliersFilters vm={vm} />
      <SuppliersTable vm={vm} />
      {confirmDialog}
    </div>
  );
}
